import csv
from datetime import datetime
from pathlib import Path

from peewee import IntegrityError

from app.database import db
from app.models.user import User
from app.services.db_errors import classify_user_integrity_error
from app.services.errors import NotFoundError, ValidationError
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

    def bulk_load_users(self, filename: str = "users.csv") -> int:
        data_file = Path(__file__).resolve().parents[2] / "data" / filename
        if not data_file.exists() or not data_file.is_file():
            raise ValidationError(
                f"File '{filename}' not found",
                details={"fields": ["file"]},
            )

        inserted = 0
        with data_file.open(newline="") as file_obj:
            reader = csv.DictReader(file_obj)

            for row in reader:
                username = (row.get("username") or "").strip()
                email = (row.get("email") or "").strip()
                if not username or not email:
                    continue

                payload = {
                    "username": username,
                    "email": email,
                }

                parsed_id = self._parse_optional_int(row.get("id"))
                if parsed_id is not None:
                    payload["id"] = parsed_id

                parsed_created_at = self._parse_created_at(row.get("created_at"))
                if parsed_created_at is not None:
                    payload["created_at"] = parsed_created_at

                # Duplicate rows can appear on repeated loads; skip conflicts.
                try:
                    result = User.insert(payload).on_conflict_ignore().execute()
                    if result:
                        inserted += 1
                except IntegrityError:
                    continue

        self._sync_user_id_sequence()
        return inserted

    @staticmethod
    def _parse_optional_int(value: object) -> int | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    @staticmethod
    def _parse_created_at(value: object) -> datetime | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _sync_user_id_sequence() -> None:
        db.execute_sql(
            """
            SELECT setval(
                pg_get_serial_sequence('"user"', 'id'),
                COALESCE((SELECT MAX(id) FROM "user"), 1),
                (SELECT COUNT(*) > 0 FROM "user")
            )
            """
        )
