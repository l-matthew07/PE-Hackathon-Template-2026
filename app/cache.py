import logging
import json

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings

_client = None
_logger = logging.getLogger(__name__)


def _get_client():
    global _client
    if _client is None:
        redis_url = get_settings().redis_url
        _client = Redis.from_url(redis_url, decode_responses=True)
    return _client


def cache_get(key: str) -> str | None:
    try:
        return _get_client().get(key)
    except RedisError as exc:
        _logger.warning("Redis cache_get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> None:
    try:
        _get_client().setex(key, ttl_seconds, value)
    except RedisError as exc:
        _logger.warning("Redis cache_set failed for key=%s: %s", key, exc)
        return


def cache_delete(key: str) -> None:
    try:
        _get_client().delete(key)
    except RedisError as exc:
        _logger.warning("Redis cache_delete failed for key=%s: %s", key, exc)
        return


def cache_get_json(key: str) -> object | None:
    raw = cache_get(key)
    if raw is None:
        return None

    try:
        return json.loads(raw)
    except ValueError as exc:
        _logger.warning("Redis cache_get_json invalid JSON for key=%s: %s", key, exc)
        return None


def cache_set_json(key: str, value: object, ttl_seconds: int = 3600) -> None:
    try:
        raw = json.dumps(value)
    except (TypeError, ValueError) as exc:
        _logger.warning("Redis cache_set_json serialization failed for key=%s: %s", key, exc)
        return

    cache_set(key, raw, ttl_seconds)
