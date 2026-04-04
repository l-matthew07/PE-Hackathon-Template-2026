import logging
import time
import uuid

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.config import get_settings
from app.database import db, init_db
from app.lib.api import error_response
from app.logging_config import setup_logging
from app.routes import register_routes

_logger = logging.getLogger(__name__)


def create_app():
    load_dotenv()
    get_settings()

    app = Flask(__name__)

    # Structured JSON logging — must be first so all subsequent logs are JSON
    setup_logging(app)

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee
    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    db.connect(reuse_if_open=True)
    try:
        # Keep startup resilient in environments where migrations were not run yet.
        db.create_tables([User, Url, Event], safe=True)
    finally:
        if not db.is_closed():
            db.close()

    register_routes(app)

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return error_response(exc.description, "HTTP_ERROR", exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        app.logger.exception("Unhandled application error", exc_info=exc)
        return error_response("Internal server error", "INTERNAL_ERROR", 500)

    from app.routes.metrics import (
        active_requests,
        http_request_duration_seconds,
        http_requests_total,
    )

    @app.before_request
    def _before():
        g.start_time = time.time()
        g.request_id = str(uuid.uuid4())
        active_requests.inc()

    @app.after_request
    def _after(response):
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

    return app
