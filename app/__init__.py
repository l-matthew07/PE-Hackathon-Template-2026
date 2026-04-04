import os

from dotenv import load_dotenv
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

from app.database import init_db
from app.routes import register_routes


def create_app():
    load_dotenv()

    app = Flask(__name__)

    PrometheusMetrics(
        app,
        group_by="url_rule",
        default_labels={"instance": os.environ.get("HOSTNAME", "unknown")},
    )

    init_db(app)

    from app import models  # noqa: F401 - registers models with Peewee

    register_routes(app)

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
