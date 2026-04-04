import json
import secrets
import string
from datetime import datetime

from peewee import IntegrityError

from app.models.event import Event
from app.models.url import Url
from app.services.db_errors import classify_url_integrity_error
from app.services.errors import InternalError, NotFoundError
from app.services.schemas import parse_url_create, parse_url_update

_ALPHABET = string.ascii_letters + string.digits


class UrlsService:
    @staticmethod
    def _generate_code(length: int = 6) -> str:
        return "".join(secrets.choice(_ALPHABET) for _ in range(length))

    def create_url(self, payload: dict) -> Url:
        parsed = parse_url_create(payload)
        short_code = parsed.short_code

        if not short_code:
            for _ in range(10):
                candidate = self._generate_code()
                if Url.get_or_none(Url.short_code == candidate) is None:
                    short_code = candidate
                    break

        if not short_code:
            raise InternalError("Could not generate short_code")

        try:
            url = Url.create(
                user_id=parsed.user_id,
                short_code=short_code,
                original_url=parsed.original_url,
                title=parsed.title,
                updated_at=datetime.utcnow(),
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
                    timestamp=datetime.utcnow(),
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

        url.updated_at = datetime.utcnow()
        try:
            url.save()
        except IntegrityError as exc:
            classify_url_integrity_error(exc)
            raise

        return url
