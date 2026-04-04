from flask import request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.lib.api import error_response, list_response
from app.lib.utils import format_datetime, normalize_pagination
from app.models.user import User
from app.services.errors import ServiceError
from app.services.schemas import (
    BulkLoadResponse,
    ErrorEnvelope,
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
    user = User.get_or_none(User.id == path.user_id)
    if user is None:
        return error_response("User not found", "NOT_FOUND", 404)
    return _serialize_user(user), 200


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

    return _serialize_user(user), 200


@users_bp.delete("/<int:user_id>")
def delete_user(path: UserIdPath):
    deleted = User.delete().where(User.id == path.user_id).execute()
    if deleted == 0:
        return "", 204
    return "", 204


@users_bp.post("/bulk", responses={200: BulkLoadResponse, 400: ErrorEnvelope})
def bulk_load_users():
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("file") or "users.csv").strip() or "users.csv"
    requested_count = payload.get("row_count")
    try:
        loaded_count = users_service.bulk_load_users(filename)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)
    return {"file": filename, "row_count": requested_count, "loaded": loaded_count}, 200