import logging

from flask import Blueprint, jsonify, redirect, request

from app.cache import cache_get, cache_set
from app.config import get_settings
from app.lib.api import error_response
from app.models.url import Url
from app.routes.bulk import register_bulk_load_endpoint
from app.routes.metrics import url_shortener_redirects_total
from app.services.errors import ServiceError
from app.services.shortener_service import ShortenerService

logger = logging.getLogger(__name__)

shortener_bp = Blueprint("shortener", __name__)
shortener_service = ShortenerService()
register_bulk_load_endpoint(
    shortener_bp,
    shortener_service.bulk_load_urls,
    route="/shorten/bulk",
    default_file="urls.csv",
)


def _base_url() -> str:
    configured = get_settings().app_base_url
    if configured:
        return configured.rstrip("/")
    return request.host_url.rstrip("/")


@shortener_bp.post("/shorten")
def shorten_url():
    payload = request.get_json(silent=True) or {}

    try:
        url = shortener_service.create_short_url(payload)
    except ServiceError as exc:
        logger.warning("URL validation failed: %s", exc.message)
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    logger.info("URL shortened: %s -> %s", url.original_url, url.short_code)
    return (
        jsonify(
            original_url=url.original_url,
            short_code=url.short_code,
            short_url=f"{_base_url()}/{url.short_code}",
        ),
        201,
    )


@shortener_bp.get("/<short_code>")
def resolve_short_url(short_code: str):
    cache_key = f"short-url:{short_code}"
    cached_url = cache_get(cache_key)
    if cached_url:
        url_shortener_redirects_total.labels(status="hit").inc()
        return redirect(cached_url, code=302)

    url = Url.get_or_none((Url.short_code == short_code) & (Url.is_active == True))
    if url is None:
        logger.warning("Short URL not found: %s", short_code)
        url_shortener_redirects_total.labels(status="miss").inc()
        return error_response("Short URL not found", "NOT_FOUND", 404)

    shortener_service.capture_click_event(url, short_code)
    url_shortener_redirects_total.labels(status="hit").inc()

    cache_set(cache_key, url.original_url, ttl_seconds=3600)
    return redirect(url.original_url, code=302)
