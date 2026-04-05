import json
import secrets
import string
from datetime import UTC, datetime
from pathlib import Path
import csv

from peewee import IntegrityError

from app.models.event import Event
from app.models.url import Url
from app.services.db_errors import (
    classify_url_integrity_error,
    is_url_original_url_conflict,
    is_url_short_code_conflict,
)
from app.services.errors import InternalError, NotFoundError
from app.services.schemas import parse_url_create, parse_url_update

_ALPHABET = string.ascii_letters + string.digits


class UrlsService:
    @staticmethod
    def _generate_code(length: int = 8) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(length))

    def create_url(self, payload: dict) -> Url:
        parsed = parse_url_create(payload)
        short_code = parsed.short_code
        url = None

        if not short_code:
            existing = Url.get_or_none(Url.original_url == parsed.original_url)
            if existing is not None:
                return existing

            for _ in range(10):
                candidate = self._generate_code()
                try:
                    url = Url.create(
                        user_id=parsed.user_id,
                        short_code=candidate,
                        original_url=parsed.original_url,
                        title=parsed.title,
                        updated_at=datetime.now(UTC),
                    )
                    short_code = candidate
                    break
                except IntegrityError as exc:
                    if is_url_short_code_conflict(exc):
                        continue
                    if is_url_original_url_conflict(exc):
                        existing = Url.get_or_none(Url.original_url == parsed.original_url)
                        if existing is not None:
                            return existing
                    classify_url_integrity_error(exc)
                    raise

        if not short_code:
            raise InternalError("Could not generate short_code")

        if url is None:
            try:
                url = Url.create(
                    user_id=parsed.user_id,
                    short_code=short_code,
                    original_url=parsed.original_url,
                    title=parsed.title,
                    updated_at=datetime.now(UTC),
                )
            except IntegrityError as exc:
                classify_url_integrity_error(exc)
                raise

        if parsed.user_id is not None:
            try:
                Event.create(
                    url_id=url.id,
                    user_id=parsed.user_id,
                    event_type="created",
                    timestamp=datetime.now(UTC),
                    details=json.dumps(
                        {"short_code": url.short_code, "original_url": url.original_url}
                    ),
                )
            except IntegrityError:
                pass

        return url

    def update_url(self, url_id: int, payload: dict) -> Url:
        url = Url.get_or_none(Url.id == url_id)
        if url is None:
            raise NotFoundError("URL not found")

        parsed = parse_url_update(payload)
        if parsed.title is not None:
            url.title = parsed.title
        if parsed.original_url is not None:
            url.original_url = parsed.original_url
        if parsed.is_active is not None:
            url.is_active = parsed.is_active

        url.updated_at = datetime.now(UTC)
        try:
            url.save()
        except IntegrityError as exc:
            classify_url_integrity_error(exc)
            raise

        return url

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
    def _parse_datetime(value: object) -> datetime | None:
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
    def _parse_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        return text in {"1", "true", "t", "yes", "y", "on"}

    def bulk_load_urls(self, filename: str = "urls.csv") -> int:
        data_file = Path(__file__).resolve().parents[2] / "data" / filename
        if not data_file.exists() or not data_file.is_file():
            from app.services.errors import ValidationError

            raise ValidationError(
                f"File '{filename}' not found",
                details={"fields": ["file"]},
            )

        inserted = 0
        with data_file.open(newline="") as file_obj:
            reader = csv.DictReader(file_obj)

            for row in reader:
                short_code = (row.get("short_code") or "").strip()
                original_url = (row.get("original_url") or "").strip()
                if not short_code or not original_url:
                    continue

                payload = {
                    "short_code": short_code,
                    "original_url": original_url,
                    "title": (row.get("title") or "").strip() or None,
                    "is_active": self._parse_bool(row.get("is_active")),
                }

                parsed_id = self._parse_optional_int(row.get("id"))
                if parsed_id is not None:
                    payload["id"] = parsed_id

                parsed_user_id = self._parse_optional_int(row.get("user_id"))
                if parsed_user_id is not None:
                    payload["user_id"] = parsed_user_id

                parsed_created_at = self._parse_datetime(row.get("created_at"))
                if parsed_created_at is not None:
                    payload["created_at"] = parsed_created_at

                parsed_updated_at = self._parse_datetime(row.get("updated_at"))
                if parsed_updated_at is not None:
                    payload["updated_at"] = parsed_updated_at

                try:
                    result = Url.insert(payload).on_conflict_ignore().execute()
                    if result:
                        inserted += 1
                except IntegrityError:
                    continue

        self._sync_url_id_sequence()
        return inserted

    @staticmethod
    def _sync_url_id_sequence() -> None:
        from app.database import db

        db.execute_sql(
            """
            SELECT setval(
                pg_get_serial_sequence('url', 'id'),
                COALESCE((SELECT MAX(id) FROM url), 1),
                (SELECT COUNT(*) > 0 FROM url)
            )
            """
        )
