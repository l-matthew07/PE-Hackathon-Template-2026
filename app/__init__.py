import logging
import os
import time
import uuid

from dotenv import load_dotenv
from flask import g, jsonify, redirect, request
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from werkzeug.exceptions import HTTPException

from app.config import get_settings
from app.database import db, init_db
from app.lib.api import error_response
from app.logging_config import setup_logging
from app.routes import register_routes

_logger = logging.getLogger(__name__)


STARTUP_SCHEMA_LOCK_ID = 2 # random number to lock db on startup


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

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    db.connect(reuse_if_open=True)
    try:
        # Prevent startup races when multiple gunicorn workers/replicas boot simultaneously.
        db.execute_sql("SELECT pg_advisory_lock(%s)", (STARTUP_SCHEMA_LOCK_ID,))
        try:
            # Keep startup resilient in environments where migrations were not run yet.
            db.create_tables([User, Url, Event], safe=True)
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
        if g.get("skip_metrics"):
            return response

        active_requests.dec()
        duration = time.time() - g.start_time
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

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/docs")
    def scalar_docs():
        return redirect("/openapi/scalar", code=302) # slightly cursed but works

    return app
