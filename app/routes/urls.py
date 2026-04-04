import json
import secrets
import string
from datetime import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.lib.utils import (
    format_datetime,
    parse_bool,
    parse_pagination,
)
from app.models.event import Event
from app.models.url import Url

urls_bp = Blueprint("urls", __name__, url_prefix="/urls")

_ALPHABET = string.ascii_letters + string.digits


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


def _generate_code(length: int = 6) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


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
    return jsonify([_serialize_url(url) for url in urls]), 200


@urls_bp.get("/<int:url_id>")
def get_url(url_id: int):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404
    return jsonify(_serialize_url(url)), 200


@urls_bp.post("")
def create_url():
    payload = request.get_json(silent=True) or {}

    original_url = (payload.get("original_url") or payload.get("url") or "").strip()
    title = payload.get("title")
    user_id = payload.get("user_id")
    short_code = (payload.get("short_code") or "").strip()

    if not original_url:
        return jsonify(error="original_url is required"), 400

    if not short_code:
        for _ in range(10):
            candidate = _generate_code()
            if Url.get_or_none(Url.short_code == candidate) is None:
                short_code = candidate
                break
        if not short_code:
            return jsonify(error="Could not generate short_code"), 500

    try:
        url = Url.create(
            user_id=user_id,
            short_code=short_code,
            original_url=original_url,
            title=title,
            updated_at=datetime.utcnow(),
        )
    except IntegrityError as exc:
        return jsonify(error=str(exc)), 400

    # Capture creation analytics for event endpoints/challenges.
    if user_id is not None:
        try:
            Event.create(
                url_id=url.id,
                user_id=user_id,
                event_type="created",
                timestamp=datetime.utcnow(),
                details=json.dumps(
                    {"short_code": url.short_code, "original_url": url.original_url}
                ),
            )
        except IntegrityError:
            pass

    return jsonify(_serialize_url(url)), 201


@urls_bp.put("/<int:url_id>")
def update_url(url_id: int):
    url = Url.get_or_none(Url.id == url_id)
    if url is None:
        return jsonify(error="URL not found"), 404

    payload = request.get_json(silent=True) or {}

    if "title" in payload:
        url.title = payload.get("title")
    if "original_url" in payload:
        url.original_url = payload.get("original_url")
    if "is_active" in payload:
        url.is_active = bool(payload.get("is_active"))

    url.updated_at = datetime.utcnow()
    url.save()

    return jsonify(_serialize_url(url)), 200


@urls_bp.delete("/<int:url_id>")
def delete_url(url_id: int):
    deleted = Url.delete().where(Url.id == url_id).execute()
    if deleted == 0:
        return "", 204
    return "", 204