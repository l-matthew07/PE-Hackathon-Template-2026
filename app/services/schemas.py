import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse

from app.services.errors import ValidationError

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class UserCreatePayload:
    username: str
    email: str


@dataclass(frozen=True)
class UserUpdatePayload:
    username: str | None
    email: str | None


@dataclass(frozen=True)
class UrlCreatePayload:
    original_url: str
    title: str | None
    user_id: int | None
    short_code: str | None


@dataclass(frozen=True)
class UrlUpdatePayload:
    original_url: str | None
    title: str | None
    is_active: bool | None


@dataclass(frozen=True)
class EventCreatePayload:
    url_id: int
    user_id: int
    event_type: str
    timestamp: datetime
    details: str | None


@dataclass(frozen=True)
class ShortenPayload:
    original_url: str
    title: str | None


def _clean_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _require_int(name: str, value: object) -> int:
    if value is None:
        raise ValidationError(f"{name} is required", details={"fields": [name]})
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer", details={"fields": [name]})


def _optional_int(name: str, value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer", details={"fields": [name]})


def _optional_bool(name: str, value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False

    raise ValidationError(f"{name} must be a boolean", details={"fields": [name]})


def _validate_http_url(name: str, value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError(
            f"{name} must be a valid http/https URL",
            details={"fields": [name]},
        )


def parse_user_create(payload: dict) -> UserCreatePayload:
    username = _clean_string(payload.get("username"))
    email = _clean_string(payload.get("email"))

    if not username or not email:
        raise ValidationError(
            "username and email are required",
            details={"fields": ["username", "email"]},
        )
    if not _EMAIL_REGEX.match(email):
        raise ValidationError("email must be valid", details={"fields": ["email"]})

    return UserCreatePayload(username=username, email=email)


def parse_user_update(payload: dict) -> UserUpdatePayload:
    if "username" not in payload and "email" not in payload:
        raise ValidationError(
            "At least one of username or email is required",
            details={"fields": ["username", "email"]},
        )

    username = _clean_string(payload.get("username")) if "username" in payload else None
    email = _clean_string(payload.get("email")) if "email" in payload else None

    if username is not None and not username:
        raise ValidationError("username cannot be empty", details={"fields": ["username"]})
    if email is not None:
        if not email:
            raise ValidationError("email cannot be empty", details={"fields": ["email"]})
        if not _EMAIL_REGEX.match(email):
            raise ValidationError("email must be valid", details={"fields": ["email"]})

    return UserUpdatePayload(username=username, email=email)


def parse_url_create(payload: dict) -> UrlCreatePayload:
    original_url = _clean_string(payload.get("original_url") or payload.get("url"))
    title = _clean_string(payload.get("title")) or None
    user_id = _optional_int("user_id", payload.get("user_id"))
    short_code = _clean_string(payload.get("short_code")) or None

    if not original_url:
        raise ValidationError(
            "original_url is required",
            details={"fields": ["original_url"]},
        )
    _validate_http_url("original_url", original_url)

    if short_code and (len(short_code) > 12 or not short_code.isalnum()):
        raise ValidationError(
            "short_code must be alphanumeric and at most 12 chars",
            details={"fields": ["short_code"]},
        )

    return UrlCreatePayload(
        original_url=original_url,
        title=title,
        user_id=user_id,
        short_code=short_code,
    )


def parse_url_update(payload: dict) -> UrlUpdatePayload:
    if not any(field in payload for field in ("title", "original_url", "is_active")):
        raise ValidationError(
            "At least one of title, original_url, or is_active is required",
            details={"fields": ["title", "original_url", "is_active"]},
        )

    title = _clean_string(payload.get("title")) if "title" in payload else None
    original_url = _clean_string(payload.get("original_url")) if "original_url" in payload else None
    is_active = _optional_bool("is_active", payload.get("is_active"))

    if original_url is not None:
        if not original_url:
            raise ValidationError("original_url cannot be empty", details={"fields": ["original_url"]})
        _validate_http_url("original_url", original_url)

    return UrlUpdatePayload(original_url=original_url, title=title, is_active=is_active)


def parse_event_create(payload: dict) -> EventCreatePayload:
    url_id = _require_int("url_id", payload.get("url_id"))
    user_id = _require_int("user_id", payload.get("user_id"))
    event_type = _clean_string(payload.get("event_type"))

    if not event_type:
        raise ValidationError("event_type is required", details={"fields": ["event_type"]})

    timestamp_raw = payload.get("timestamp")
    if timestamp_raw:
        try:
            timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError("timestamp must be ISO-8601", details={"fields": ["timestamp"]})
    else:
        timestamp = datetime.utcnow()

    details_raw = payload.get("details")
    details: str | None
    if details_raw is None or details_raw == "":
        details = None
    elif isinstance(details_raw, (dict, list)):
        details = json.dumps(details_raw)
    elif isinstance(details_raw, str):
        details = details_raw
    else:
        details = str(details_raw)

    return EventCreatePayload(
        url_id=url_id,
        user_id=user_id,
        event_type=event_type,
        timestamp=timestamp,
        details=details,
    )


def parse_shorten_payload(payload: dict) -> ShortenPayload:
    original_url = _clean_string(payload.get("url") or payload.get("original_url"))
    title = _clean_string(payload.get("title")) or None

    if not original_url:
        raise ValidationError(
            "Please provide a valid http/https URL in 'url'",
            details={"fields": ["url"]},
        )

    _validate_http_url("url", original_url)
    return ShortenPayload(original_url=original_url, title=title)
