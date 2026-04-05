import logging
import json
from collections.abc import Awaitable
from typing import cast

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
        raw = _get_client().get(key)
        return cast(str | None, raw)
    except RedisError as exc:
        _logger.warning("Redis cache_get failed for key=%s: %s", key, exc)
        return None


def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> None:
    try:
        result = _get_client().setex(key, ttl_seconds, value)
        if isinstance(result, Awaitable):
            _logger.warning("Redis cache_set received awaitable for key=%s; ensure sync Redis client is configured", key)
    except RedisError as exc:
        _logger.warning("Redis cache_set failed for key=%s: %s", key, exc)
        return


def cache_delete(key: str) -> None:
    try:
        result = _get_client().delete(key)
        if isinstance(result, Awaitable):
            _logger.warning("Redis cache_delete received awaitable for key=%s; ensure sync Redis client is configured", key)
    except RedisError as exc:
        _logger.warning("Redis cache_delete failed for key=%s: %s", key, exc)
        return


def cache_delete_prefix(prefix: str) -> None:
    try:
        keys = list(_get_client().scan_iter(match=f"{prefix}*"))
        if not keys:
            return
        result = _get_client().delete(*keys)
        if isinstance(result, Awaitable):
            _logger.warning("Redis cache_delete_prefix received awaitable for prefix=%s; ensure sync Redis client is configured", prefix)
    except RedisError as exc:
        _logger.warning("Redis cache_delete_prefix failed for prefix=%s: %s", prefix, exc)
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
