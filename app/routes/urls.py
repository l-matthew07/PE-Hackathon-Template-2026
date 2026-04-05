from flask import request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.cache import cache_delete, cache_get_json, cache_set_json
from app.config import get_settings
from app.lib.api import error_response, list_response
from app.lib.utils import (
    format_datetime,
    normalize_pagination,
)
from app.models.url import Url
from app.services.errors import ServiceError
from app.services.schemas import (
    ErrorEnvelope,
    ImportedCountResponse,
    UrlCreatePayload,
    UrlIdPath,
    UrlListQuery,
    UrlListResponse,
    UrlResponse,
    UrlUpdatePayload,
)
from app.services.urls_service import UrlsService

urls_tag = Tag(name="urls")
urls_bp = APIBlueprint("urls", __name__, url_prefix="/urls", abp_tags=[urls_tag])

urls_service = UrlsService()


def _url_cache_key(url_id: int) -> str:
    return f"url:{url_id}"


def _extract_user_id(url: Url) -> int | None:
    raw_value = getattr(url, "user_id_id", None)
    if raw_value is not None:
        return int(raw_value)

    relation_value = getattr(url, "user_id", None)
    if relation_value is None:
        return None
    if isinstance(relation_value, int):
        return relation_value

    return getattr(relation_value, "id", None)


def _serialize_url(url: Url) -> dict:
    return {
        "id": url.id,
        "user_id": _extract_user_id(url),
        "short_code": url.short_code,
        "original_url": url.original_url,
        "title": url.title,
        "is_active": url.is_active,
        "created_at": format_datetime(url.created_at),
        "updated_at": format_datetime(url.updated_at),
    }


@urls_bp.get("", responses={200: UrlListResponse})
def list_urls(query: UrlListQuery):
    page, per_page = normalize_pagination(query.page, query.per_page)
    offset = (page - 1) * per_page

    db_query = Url.select()

    if query.user_id is not None:
        db_query = db_query.where(Url.user_id == query.user_id)

    if query.is_active is not None:
        db_query = db_query.where(Url.is_active == query.is_active)

    urls = db_query.order_by(Url.id).limit(per_page).offset(offset)
    return list_response([_serialize_url(url) for url in urls], page, per_page)


@urls_bp.get("/<int:url_id>", responses={200: UrlResponse, 404: ErrorEnvelope})
def get_url(path: UrlIdPath):
    cache_key = _url_cache_key(path.url_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return cached_payload, 200

    url = Url.get_or_none(Url.id == path.url_id)
    if url is None:
        return error_response("URL not found", "NOT_FOUND", 404)

    payload = _serialize_url(url)
    cache_set_json(cache_key, payload, ttl_seconds=get_settings().cache_ttl_seconds)
    return payload, 200


@urls_bp.post("", responses={201: UrlResponse, 400: ErrorEnvelope, 409: ErrorEnvelope})
def create_url(body: UrlCreatePayload):
    try:
        url = urls_service.create_url(body.model_dump())
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return _serialize_url(url), 201


@urls_bp.put("/<int:url_id>", responses={200: UrlResponse, 400: ErrorEnvelope, 404: ErrorEnvelope, 409: ErrorEnvelope})
def update_url(path: UrlIdPath, body: UrlUpdatePayload):
    try:
        url = urls_service.update_url(path.url_id, body.model_dump(exclude_unset=True))
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    payload = _serialize_url(url)
    cache_delete(_url_cache_key(path.url_id))
    return payload, 200


@urls_bp.delete("/<int:url_id>")
def delete_url(path: UrlIdPath):
    Url.delete().where(Url.id == path.url_id).execute()
    cache_delete(_url_cache_key(path.url_id))
    return "", 204


@urls_bp.post("/bulk", responses={201: ImportedCountResponse, 400: ErrorEnvelope})
def bulk_load_urls():
    json_payload = request.get_json(silent=True)
    if isinstance(json_payload, dict) and "file" in json_payload:
        filename = str(json_payload.get("file") or "").strip()
        if not filename:
            return error_response(
                "file is required",
                "VALIDATION_ERROR",
                400,
                details={"fields": ["file"]},
            )

        try:
            loaded_count = urls_service.bulk_load_urls(filename=filename)
        except ServiceError as exc:
            return error_response(exc.message, exc.code, exc.status, details=exc.details)

        return {"imported": loaded_count}, 201

    uploaded_file = request.files.get("file")
    if uploaded_file is None or not uploaded_file.filename:
        return error_response(
            "multipart/form-data with a 'file' field is required",
            "VALIDATION_ERROR",
            400,
            details={"fields": ["file"]},
        )

    try:
        loaded_count = urls_service.bulk_load_urls_upload(uploaded_file)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return {"imported": loaded_count}, 201