from datetime import datetime

from peewee import IntegrityError

from app.models.event import Event
from app.services.db_errors import classify_event_integrity_error
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
