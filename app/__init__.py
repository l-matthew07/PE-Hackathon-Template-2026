import os

from dotenv import load_dotenv
from flask import jsonify, redirect
from flask_openapi3.models.info import Info
from flask_openapi3.openapi import OpenAPI
from prometheus_flask_exporter import PrometheusMetrics
from werkzeug.exceptions import HTTPException

from app.config import get_settings
from app.database import db, init_db
from app.lib.api import error_response
from app.routes import register_routes


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

    PrometheusMetrics(
        app,
        group_by="url_rule",
        default_labels={"instance": os.environ.get("HOSTNAME", "unknown")},
    )

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
        # Keep startup resilient in environments where migrations were not run yet.
        db.create_tables([User, Url, Event], safe=True)
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

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/docs")
    def scalar_docs():
        return redirect("/openapi/scalar", code=302) # slightly cursed but works

    return app
