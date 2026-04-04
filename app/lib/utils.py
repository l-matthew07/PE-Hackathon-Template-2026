from datetime import datetime

from flask import request


def format_datetime(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def parse_pagination(default_per_page: int = 100) -> tuple[int, int]:
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(
        1,
        request.args.get("per_page", default=default_per_page, type=int)
        or default_per_page,
    )
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
