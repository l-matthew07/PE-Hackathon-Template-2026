import csv
from datetime import datetime
from pathlib import Path

from peewee import IntegrityError

from app.database import db
from app.models.event import Event
from app.services.db_errors import classify_event_integrity_error
from app.services.errors import ValidationError
from app.services.schemas import parse_event_create


class EventsService:
    def create_event(self, payload: dict) -> Event:
        parsed = parse_event_create(payload)

        try:
            return Event.create(
                url_id=parsed.url_id,
                user_id=parsed.user_id,
                event_type=parsed.event_type,
                timestamp=parsed.timestamp,
                details=parsed.details,
            )
        except IntegrityError as exc:
            classify_event_integrity_error(exc)
            raise

    def bulk_load_events(self, filename: str = "events.csv") -> int:
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
                event_type = (row.get("event_type") or "").strip()
                timestamp = self._parse_timestamp(row.get("timestamp"))
                user_id = self._parse_required_int(row.get("user_id"))
                url_id = self._parse_required_int(row.get("url_id"))
                if not event_type or timestamp is None or user_id is None or url_id is None:
                    continue

                payload = {
                    "event_type": event_type,
                    "timestamp": timestamp,
                    "user_id": user_id,
                    "url_id": url_id,
                    "details": row.get("details"),
                }

                parsed_id = self._parse_required_int(row.get("id"))
                if parsed_id is not None:
                    payload["id"] = parsed_id

                try:
                    result = Event.insert(payload).on_conflict_ignore().execute()
                    if result:
                        inserted += 1
                except IntegrityError:
                    continue

        self._sync_event_id_sequence()
        return inserted

    @staticmethod
    def _parse_required_int(value: object) -> int | None:
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
    def _parse_timestamp(value: object) -> datetime | None:
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
    def _sync_event_id_sequence() -> None:
        db.execute_sql(
            """
            SELECT setval(
                pg_get_serial_sequence('event', 'id'),
                COALESCE((SELECT MAX(id) FROM event), 1),
                (SELECT COUNT(*) > 0 FROM event)
            )
            """
        )
