import json
import secrets
import string
from datetime import datetime

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
                        updated_at=datetime.utcnow(),
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
