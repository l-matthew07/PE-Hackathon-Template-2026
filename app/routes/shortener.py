from flask import Blueprint, jsonify, redirect, request

from app.cache import cache_get, cache_set
from app.config import get_settings
from app.lib.api import error_response
from app.models.url import Url
from app.services.errors import ServiceError
from app.services.shortener_service import ShortenerService

shortener_bp = Blueprint("shortener", __name__)
shortener_service = ShortenerService()


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
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

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
        return redirect(cached_url, code=302)

    url = Url.get_or_none((Url.short_code == short_code) & (Url.is_active == True))
    if url is None:
        return error_response("Short URL not found", "NOT_FOUND", 404)

    shortener_service.capture_click_event(url, short_code)

    cache_set(cache_key, url.original_url, ttl_seconds=3600)
    return redirect(url.original_url, code=302)
