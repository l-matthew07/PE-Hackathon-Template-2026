from dotenv import load_dotenv
from flask import Flask, jsonify

from app.database import db, init_db
from app.routes import register_routes


def create_app():
    load_dotenv()

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

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    return app
