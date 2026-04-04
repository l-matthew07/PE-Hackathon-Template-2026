from peewee import DatabaseProxy, Model, PostgresqlDatabase

from app.config import get_settings

db = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = db


def init_db(app):
    settings = get_settings()
    database = PostgresqlDatabase(
        settings.database_name,
        host=settings.database_host,
        port=settings.database_port,
        user=settings.database_user,
        password=settings.database_password,
    )
    db.initialize(database)

    @app.before_request
    def _db_connect():
        if not db.is_closed():
            db.close()
        db.connect()

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()
