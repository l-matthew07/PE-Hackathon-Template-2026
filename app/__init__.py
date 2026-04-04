import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException

from app.config import get_settings
from app.database import db, init_db
from app.lib.api import error_response
from app.routes import register_routes


def create_app():
    load_dotenv()
    get_settings()

    app = Flask(__name__)

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
        return response

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
