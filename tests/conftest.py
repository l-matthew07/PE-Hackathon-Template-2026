"""Shared fixtures for the test suite.

Uses an in-memory SQLite database so tests run without Postgres/Redis.
"""

import os

# Set env vars BEFORE any app code is imported so Settings picks them up.
os.environ.update(
    {
        "DATABASE_NAME": ":memory:",
        "DATABASE_HOST": "",
        "DATABASE_PORT": "0",
        "DATABASE_USER": "",
        "DATABASE_PASSWORD": "",
        "REDIS_URL": "redis://localhost:6379/0",
        "APP_BASE_URL": "http://localhost",
    }
)

import pytest
from peewee import SqliteDatabase

from app.database import db

# Shared in-memory SQLite — same connection reused everywhere
_test_db = SqliteDatabase(":memory:")


@pytest.fixture(autouse=True)
def _setup_db():
    """Bind models to an in-memory SQLite DB and create tables fresh per test."""
    from app.models.event import Event
    from app.models.url import Url
    from app.models.user import User

    _test_db.bind([User, Url, Event])
    db.initialize(_test_db)
    _test_db.connect(reuse_if_open=True)
    _test_db.create_tables([User, Url, Event])

    yield

    _test_db.drop_tables([Event, Url, User])
    if not _test_db.is_closed():
        _test_db.close()


@pytest.fixture()
def app(_setup_db):
    """Create a minimal OpenAPI app matching production setup."""
    import uuid

    from flask import g, jsonify
    from flask_openapi3.models.info import Info
    from flask_openapi3.openapi import OpenAPI
    from werkzeug.exceptions import HTTPException

    from app.lib.api import error_response
    from app.routes.events import events_bp
    from app.routes.urls import urls_bp
    from app.routes.users import users_bp

    info = Info(title="Test", version="1.0.0")
    test_app = OpenAPI(__name__, info=info)
    test_app.config["TESTING"] = True

    # Register blueprints
    test_app.register_blueprint(users_bp)
    test_app.register_blueprint(urls_bp)
    test_app.register_blueprint(events_bp)

    @test_app.route("/health")
    def health():
        return jsonify(status="ok")

    @test_app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return error_response(exc.description or "Unknown error", "HTTP_ERROR", exc.code or 500)

    @test_app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        return error_response("Internal server error", "INTERNAL_ERROR", 500)

    @test_app.before_request
    def _open():
        db.connect(reuse_if_open=True)
        g.request_id = str(uuid.uuid4())

    @test_app.teardown_appcontext
    def _close(exc):
        # Don't close — keep the same in-memory connection alive
        pass

    return test_app


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()
