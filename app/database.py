import logging

from peewee import DatabaseProxy, Model, PostgresqlDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)

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
    try:
        db.initialize(database)
    except Exception:
        logger.error("Failed to connect to database at %s:%s", settings.database_host, settings.database_port)
        raise

    logger.info("Database initialised: %s@%s:%s", settings.database_name, settings.database_host, settings.database_port)

    from app.models.url import Url
    with database:
        database.create_tables([Url], safe=True)

    @app.before_request
    def _db_connect():
        if not db.is_closed():
            db.close()
        db.connect()

    @app.teardown_appcontext
    def _db_close(exc):
        if not db.is_closed():
            db.close()
