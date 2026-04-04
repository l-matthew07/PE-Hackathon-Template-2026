from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.lib.utils import format_datetime, parse_pagination
from app.models.user import User

users_bp = Blueprint("users", __name__, url_prefix="/users")

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
    return jsonify([_serialize_user(user) for user in users]), 200


@users_bp.get("/<int:user_id>")
def get_user(user_id: int):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404
    return jsonify(_serialize_user(user)), 200


@users_bp.post("")
def create_user():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()

    if not username or not email:
        return jsonify(error="username and email are required"), 400

    try:
        user = User.create(username=username, email=email)
    except IntegrityError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(_serialize_user(user)), 201


@users_bp.put("/<int:user_id>")
def update_user(user_id: int):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404

    payload = request.get_json(silent=True) or {}

    username = payload.get("username")
    email = payload.get("email")

    if username is not None:
        user.username = str(username).strip()
    if email is not None:
        user.email = str(email).strip()

    try:
        user.save()
    except IntegrityError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(_serialize_user(user)), 200


@users_bp.delete("/<int:user_id>")
def delete_user(user_id: int):
    deleted = User.delete().where(User.id == user_id).execute()
    if deleted == 0:
        return "", 204
    return "", 204