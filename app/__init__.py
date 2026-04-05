import logging
import os
import json
import time
import uuid
from datetime import UTC, datetime

from dotenv import load_dotenv
from flask import g, jsonify, redirect, request
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from prometheus_flask_exporter import PrometheusMetrics
from redis import Redis
from redis.exceptions import RedisError
from werkzeug.exceptions import HTTPException

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import get_settings
from app.database import db, init_db
from app.lib.api import error_response
from app.logging_config import setup_logging
from app.cache import cache_get, cache_set
from app.routes import register_routes

_logger = logging.getLogger(__name__)


STARTUP_SCHEMA_LOCK_ID = 2 # random number to lock db on startup


def _resolve_limiter_storage_uri(redis_url: str) -> str:
    """Prefer Redis for distributed limiting, but degrade gracefully when unavailable."""
    try:
        client = Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return redis_url
    except (RedisError, OSError, ValueError) as exc:
        _logger.warning(
            "Redis unavailable for rate limiting; falling back to in-memory storage: %s",
            exc,
        )
        return "memory://"


def create_app():
    load_dotenv()
    get_settings()

    info = Info(
        title="MLH PE Hackathon API",
        version="1.0.0",
        description="The best URL shortener!",
    )
    app = OpenAPI(__name__, info=info)
    app.config["SCALAR_CONFIG"] = {"theme": "deepSpace"}

    # Structured JSON logging — must be first so all subsequent logs are JSON
    setup_logging(app)

    PrometheusMetrics(
        app,
        group_by="url_rule",
        default_labels={"instance": os.environ.get("HOSTNAME", "unknown")},
    )

    settings = get_settings()
    limiter_storage_uri = _resolve_limiter_storage_uri(settings.redis_url)
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri=limiter_storage_uri,
    )
    app.limiter = limiter

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models.alert import Alert
    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    db.connect(reuse_if_open=True)
    try:
        # Prevent startup races when multiple gunicorn workers/replicas boot simultaneously.
        db.execute_sql("SELECT pg_advisory_lock(%s)", (STARTUP_SCHEMA_LOCK_ID,))
        try:
            # Keep startup resilient in environments where migrations were not run yet.
            db.create_tables([User, Url, Event, Alert], safe=True)
        finally:
            db.execute_sql("SELECT pg_advisory_unlock(%s)", (STARTUP_SCHEMA_LOCK_ID,))
    finally:
        if not db.is_closed():
            db.close()

    register_routes(app)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return error_response(exc.description or "Unknown error", "HTTP_ERROR", exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled application error", exc_info=exc)
        return error_response("Internal server error", "INTERNAL_ERROR", 500)

    from app.routes.metrics import (
        active_requests,
        http_request_duration_seconds,
        http_requests_total,
        url_shortener_redirects_total,
    )

    _SKIP_PATHS = ("/admin", "/metrics", "/health", "/docs", "/openapi", "/static")

    def _should_skip():
        return request.path.startswith(_SKIP_PATHS)

    @app.before_request
    def _before():
        g.start_time = time.time()
        g.request_id = str(uuid.uuid4())
        if not _should_skip():
            active_requests.inc()
        g.skip_metrics = _should_skip()

    @app.after_request
    def _after(response):
        if getattr(g, "skip_metrics", False):
            return response

        start_time = getattr(g, "start_time", None)
        if start_time is None:
            return response

        active_requests.dec()
        duration = time.time() - start_time
        endpoint = request.endpoint or "unknown"
        http_request_duration_seconds.labels(
            method=request.method, endpoint=endpoint
        ).observe(duration)
        http_requests_total.labels(
            method=request.method,
            endpoint=endpoint,
            status_code=response.status_code,
        ).inc()

        # Structured request log — level matches severity
        status = response.status_code
        log_level = (
            logging.ERROR if status >= 500
            else logging.WARNING if status >= 400
            else logging.INFO
        )
        _logger.log(
            log_level,
            "%s %s -> %d (%.1fms)",
            request.method,
            request.path,
            status,
            duration * 1000,
            extra={
                "http_method": request.method,
                "http_path": request.path,
                "http_status": status,
                "duration_ms": round(duration * 1000, 1),
                "client_ip": request.remote_addr,
            },
        )
        return response

    @app.route("/test-error")
    def test_error():
        return "boom", 500

    @app.route("/test-slow")
    def test_slow():
        delay = min(int(request.args.get("delay", 3)), 30)
        time.sleep(delay)
        return jsonify(status="slow", delay=delay)

    @app.route("/health")
    @limiter.exempt
    def health():
        return jsonify(status="ok")

    @app.route("/docs")
    def scalar_docs():
        return redirect("/openapi/scalar", code=302) # slightly cursed but works

    @app.route("/<string:short_code>")
    def resolve_short_code(short_code: str):
        cache_key = f"short_code:{short_code}"
        original_url = cache_get(cache_key)
        resolved_url_id = None
        resolved_user_id = None

        if original_url is None:
            url_shortener_redirects_total.labels(status="miss").inc()
            url = Url.get_or_none((Url.short_code == short_code) & (Url.is_active == True))
            if url is None:
                return error_response("URL not found", "NOT_FOUND", 404)

            original_url = url.original_url
            resolved_url_id = url.id
            resolved_user_id = getattr(url, "user_id_id", None)
            cache_set(cache_key, original_url, ttl_seconds=settings.cache_ttl_seconds)
        else:
            url_shortener_redirects_total.labels(status="hit").inc()
            url = Url.get_or_none((Url.short_code == short_code) & (Url.is_active == True))
            if url is None:
                return error_response("URL not found", "NOT_FOUND", 404)
            resolved_url_id = url.id
            resolved_user_id = getattr(url, "user_id_id", None)

        if resolved_url_id is not None and resolved_user_id is not None:
            try:
                Event.create(
                    url_id=resolved_url_id,
                    user_id=resolved_user_id,
                    event_type="click",
                    timestamp=datetime.now(UTC),
                    details=json.dumps(
                        {
                            "short_code": short_code,
                            "original_url": original_url,
                            "source": "resolve_short_code",
                        }
                    ),
                )
            except Exception:
                _logger.warning("Failed to log click event for short_code=%s", short_code)

        return redirect(original_url, code=302)

    return app
