from flask import request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.cache import cache_delete, cache_get_json, cache_set_json
from app.config import get_settings
from app.lib.api import error_response, list_response
from app.lib.utils import format_datetime, normalize_pagination
from app.models.user import User
from app.services.errors import ServiceError
from app.services.schemas import (
    ErrorEnvelope,
    ImportedCountResponse,
    PaginationQuery,
    UserCreatePayload,
    UserIdPath,
    UserListResponse,
    UserResponse,
    UserUpdatePayload,
)
from app.services.users_service import UsersService

users_tag = Tag(name="users")
users_bp = APIBlueprint("users", __name__, url_prefix="/users", abp_tags=[users_tag])

users_service = UsersService()


def _user_cache_key(user_id: int) -> str:
    return f"user:{user_id}"

def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": format_datetime(user.created_at),
    }


@users_bp.get("", responses={200: UserListResponse})
def list_users(query: PaginationQuery):
    page, per_page = normalize_pagination(query.page, query.per_page)
    offset = (page - 1) * per_page
    users = User.select().order_by(User.id).limit(per_page).offset(offset)
    return list_response([_serialize_user(user) for user in users], page, per_page)


@users_bp.get("/<int:user_id>", responses={200: UserResponse, 404: ErrorEnvelope})
def get_user(path: UserIdPath):
    cache_key = _user_cache_key(path.user_id)
    cached_payload = cache_get_json(cache_key)
    if isinstance(cached_payload, dict):
        return cached_payload, 200

    user = User.get_or_none(User.id == path.user_id)
    if user is None:
        return error_response("User not found", "NOT_FOUND", 404)

    payload = _serialize_user(user)
    cache_set_json(cache_key, payload, ttl_seconds=get_settings().cache_ttl_seconds)
    return payload, 200


@users_bp.post("", responses={201: UserResponse, 400: ErrorEnvelope, 409: ErrorEnvelope})
def create_user(body: UserCreatePayload):
    try:
        user = users_service.create_user(body.model_dump())
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return _serialize_user(user), 201


@users_bp.put("/<int:user_id>", responses={200: UserResponse, 400: ErrorEnvelope, 404: ErrorEnvelope, 409: ErrorEnvelope})
def update_user(path: UserIdPath, body: UserUpdatePayload):
    try:
        user = users_service.update_user(path.user_id, body.model_dump(exclude_unset=True))
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    payload = _serialize_user(user)
    cache_delete(_user_cache_key(path.user_id))
    return payload, 200


@users_bp.delete("/<int:user_id>")
def delete_user(path: UserIdPath):
    deleted = User.delete().where(User.id == path.user_id).execute()
    cache_delete(_user_cache_key(path.user_id))
    if deleted == 0:
        return "", 204
    return "", 204


@users_bp.post("/bulk", responses={201: ImportedCountResponse, 400: ErrorEnvelope})
def bulk_load_users():
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
            loaded_count = users_service.bulk_load_users(filename=filename)
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
        loaded_count = users_service.bulk_load_users_upload(uploaded_file)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return {"imported": loaded_count}, 201