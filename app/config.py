import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default

    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    database_name: str
    database_host: str
    database_port: int
    database_user: str
    database_password: str
    redis_url: str
    app_base_url: str | None
    default_per_page: int
    max_per_page: int


_cached_settings: Settings | None = None


def get_settings() -> Settings:
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings

    default_per_page = max(1, _env_int("DEFAULT_PER_PAGE", 50))
    max_per_page = max(default_per_page, _env_int("MAX_PER_PAGE", 200))

    _cached_settings = Settings(
        database_name=os.environ.get("DATABASE_NAME", "hackathon_db"),
        database_host=os.environ.get("DATABASE_HOST", "localhost"),
        database_port=max(1, _env_int("DATABASE_PORT", 5432)),
        database_user=os.environ.get("DATABASE_USER", "postgres"),
        database_password=os.environ.get("DATABASE_PASSWORD", "postgres"),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        app_base_url=os.environ.get("APP_BASE_URL"),
        default_per_page=default_per_page,
        max_per_page=max_per_page,
    )
    return _cached_settings
