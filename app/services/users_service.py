from peewee import IntegrityError

from app.models.user import User
from app.services.db_errors import classify_user_integrity_error
from app.services.errors import NotFoundError
from app.services.schemas import parse_user_create, parse_user_update


class UsersService:
    def create_user(self, payload: dict) -> User:
        parsed = parse_user_create(payload)
        try:
            return User.create(username=parsed.username, email=parsed.email)
        except IntegrityError as exc:
            classify_user_integrity_error(exc)
            raise

    def update_user(self, user_id: int, payload: dict) -> User:
        user = User.get_or_none(User.id == user_id)
        if user is None:
            raise NotFoundError("User not found")

        parsed = parse_user_update(payload)
        if parsed.username is not None:
            user.username = parsed.username
        if parsed.email is not None:
            user.email = parsed.email

        try:
            user.save()
            return user
        except IntegrityError as exc:
            classify_user_integrity_error(exc)
            raise
