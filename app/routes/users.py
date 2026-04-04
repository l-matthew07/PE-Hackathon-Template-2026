from flask import Blueprint, jsonify, request

from app.lib.api import error_response, list_response
from app.lib.utils import format_datetime, parse_pagination
from app.models.user import User
from app.services.errors import ServiceError
from app.services.users_service import UsersService

users_bp = Blueprint("users", __name__, url_prefix="/users")

users_service = UsersService()

def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": format_datetime(user.created_at),
    }


@users_bp.get("")
def list_users():
    page, per_page = parse_pagination()
    offset = (page - 1) * per_page
    users = User.select().order_by(User.id).limit(per_page).offset(offset)
    return list_response([_serialize_user(user) for user in users], page, per_page)


@users_bp.get("/<int:user_id>")
def get_user(user_id: int):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return error_response("User not found", "NOT_FOUND", 404)
    return jsonify(_serialize_user(user)), 200


@users_bp.post("")
def create_user():
    payload = request.get_json(silent=True) or {}

    try:
        user = users_service.create_user(payload)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify(_serialize_user(user)), 201


@users_bp.post("/bulk")
def bulk_load_users():
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("file") or "file").strip()
    requested_count = payload.get("row_count")

    try:
        loaded_count = users_service.bulk_load_users(filename)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify({"file": filename, "row_count": requested_count, "loaded": loaded_count}), 201


@users_bp.put("/<int:user_id>")
def update_user(user_id: int):
    payload = request.get_json(silent=True) or {}

    try:
        user = users_service.update_user(user_id, payload)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify(_serialize_user(user)), 200


@users_bp.delete("/<int:user_id>")
def delete_user(user_id: int):
    deleted = User.delete().where(User.id == user_id).execute()
    if deleted == 0:
        return "", 204
    return "", 204