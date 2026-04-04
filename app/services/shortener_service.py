import json
import secrets
import string
from datetime import datetime

from peewee import IntegrityError

from app.models.event import Event
from app.models.url import Url
from app.services.errors import InternalError
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
