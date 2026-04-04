import csv
import json
import secrets
import string
from datetime import datetime
from pathlib import Path

from peewee import IntegrityError

from app.database import db
from app.models.event import Event
from app.models.url import Url
from app.services.errors import InternalError, ValidationError
from app.services.schemas import parse_shorten_payload

_ALPHABET = string.ascii_letters + string.digits


class ShortenerService:
    @staticmethod
    def _generate_code(length: int = 6) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(length))

    def create_short_url(self, payload: dict) -> Url:
        parsed = parse_shorten_payload(payload)

        for _ in range(10):
            code = self._generate_code()
            try:
                return Url.create(
                    original_url=parsed.original_url,
                    short_code=code,
                    title=parsed.title,
                    updated_at=datetime.utcnow(),
                )
            except IntegrityError:
                continue

        raise InternalError("Could not generate a unique short code. Please retry.")

    def capture_click_event(self, url: Url, short_code: str) -> None:
        if url.user_id is None:
            return

        try:
            Event.create(
                url_id=url.id,
                user_id=url.user_id,
                event_type="click",
                timestamp=datetime.utcnow(),
                details=json.dumps({"short_code": short_code}),
            )
        except IntegrityError:
            pass

    def bulk_load_urls(self, filename: str = "urls.csv") -> int:
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

    @staticmethod
    def _sync_url_id_sequence() -> None:
        db.execute_sql(
            """
            SELECT setval(
                pg_get_serial_sequence('url', 'id'),
                COALESCE((SELECT MAX(id) FROM url), 1),
                (SELECT COUNT(*) > 0 FROM url)
            )
            """
        )
