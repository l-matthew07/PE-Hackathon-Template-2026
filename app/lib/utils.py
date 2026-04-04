from datetime import datetime

from flask import request

from app.config import get_settings


def format_datetime(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def parse_pagination(default_per_page: int = 100) -> tuple[int, int]:
    settings = get_settings()
    configured_default = default_per_page or settings.default_per_page
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    requested_per_page = (
        request.args.get("per_page", default=configured_default, type=int)
        or configured_default
    )
    per_page = min(settings.max_per_page, max(1, requested_per_page))
    return page, per_page


def parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default
