from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.lib.api import error_response, list_response
from app.lib.utils import (
    format_datetime,
    normalize_pagination,
)
from app.models.url import Url
from app.services.errors import ServiceError
from app.services.schemas import (
    ErrorEnvelope,
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
    url = Url.get_or_none(Url.id == path.url_id)
    if url is None:
        return error_response("URL not found", "NOT_FOUND", 404)
    return _serialize_url(url), 200


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

    return _serialize_url(url), 200


@urls_bp.delete("/<int:url_id>")
def delete_url(path: UrlIdPath):
    Url.delete().where(Url.id == path.url_id).execute()
    return "", 204