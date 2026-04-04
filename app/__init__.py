import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request

from app.database import init_db
from app.routes import register_routes


def create_app():
    load_dotenv()

    app = Flask(__name__)

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee

    register_routes(app)

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
