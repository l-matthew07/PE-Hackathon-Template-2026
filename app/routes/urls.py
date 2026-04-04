from flask import Blueprint, jsonify, request

from app.lib.api import error_response, list_response
from app.lib.utils import (
    format_datetime,
    parse_bool,
    parse_pagination,
)
from app.models.url import Url
from app.services.errors import ServiceError
from app.services.urls_service import UrlsService

urls_bp = Blueprint("urls", __name__, url_prefix="/urls")

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


@urls_bp.get("")
def list_urls():
    page, per_page = parse_pagination()
    offset = (page - 1) * per_page

    query = Url.select()

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Url.user_id == user_id)

    is_active = request.args.get("is_active")
    if is_active is not None:
        query = query.where(Url.is_active == parse_bool(is_active))

    urls = query.order_by(Url.id).limit(per_page).offset(offset)
    return list_response([_serialize_url(url) for url in urls], page, per_page)


@urls_bp.get("/<int:url_id>")
def get_url(url_id: int):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return error_response("URL not found", "NOT_FOUND", 404)
    return jsonify(_serialize_url(url)), 200


@urls_bp.post("")
def create_url():
    payload = request.get_json(silent=True) or {}

    try:
        url = urls_service.create_url(payload)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify(_serialize_url(url)), 201


@urls_bp.put("/<int:url_id>")
def update_url(url_id: int):
    payload = request.get_json(silent=True) or {}

    try:
        url = urls_service.update_url(url_id, payload)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify(_serialize_url(url)), 200


@urls_bp.delete("/<int:url_id>")
def delete_url(url_id: int):
    deleted = Url.delete().where(Url.id == url_id).execute()
    if deleted == 0:
        return "", 204
    return "", 204