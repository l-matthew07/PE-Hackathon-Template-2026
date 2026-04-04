from flask import redirect, request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.cache import cache_get, cache_set
from app.config import get_settings
from app.lib.api import error_response
from app.models.url import Url
from app.services.errors import ServiceError
from app.services.schemas import (
    BulkLoadBody,
    BulkLoadResponse,
    ErrorEnvelope,
    ShortCodePath,
    ShortenPayload,
    ShortenResponse,
)
from app.services.shortener_service import ShortenerService

shortener_tag = Tag(name="shortener")
shortener_bp = APIBlueprint("shortener", __name__, abp_tags=[shortener_tag])
shortener_service = ShortenerService()


def _base_url() -> str:
    configured = get_settings().app_base_url
    if configured:
        return configured.rstrip("/")
    return request.host_url.rstrip("/")


@shortener_bp.post("/shorten", responses={201: ShortenResponse, 400: ErrorEnvelope, 409: ErrorEnvelope})
def shorten_url(body: ShortenPayload):
    try:
        url = shortener_service.create_short_url(body.model_dump())
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return (
        {
            "original_url": url.original_url,
            "short_code": url.short_code,
            "short_url": f"{_base_url()}/{url.short_code}",
        },
        201,
    )


@shortener_bp.get("/<short_code>", responses={404: ErrorEnvelope})
def resolve_short_url(path: ShortCodePath):
    cache_key = f"short-url:{path.short_code}"
    cached_url = cache_get(cache_key)
    if cached_url:
        return redirect(cached_url, code=302)

    url = Url.get_or_none((Url.short_code == path.short_code) & (Url.is_active == True))
    if url is None:
        return error_response("Short URL not found", "NOT_FOUND", 404)

    shortener_service.capture_click_event(url, path.short_code)

    cache_set(cache_key, url.original_url, ttl_seconds=3600)
    return redirect(url.original_url, code=302)


@shortener_bp.post("/shorten/bulk", responses={200: BulkLoadResponse, 400: ErrorEnvelope})
def bulk_load_urls(body: BulkLoadBody):
    filename = (body.file or "urls.csv").strip() or "urls.csv"
    try:
        loaded_count = shortener_service.bulk_load_urls(filename)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)
    return {"file": filename, "row_count": body.row_count, "loaded": loaded_count}, 200
