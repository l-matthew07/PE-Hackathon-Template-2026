from peewee import IntegrityError

from app.services.errors import ConflictError, ValidationError


def _extract_constraint_name(exc: IntegrityError) -> str | None:
    current = exc
    visited: set[int] = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        diag = getattr(current, "diag", None)
        if diag is not None:
            constraint_name = getattr(diag, "constraint_name", None)
            if constraint_name:
                return str(constraint_name)

        for attr in ("orig", "__cause__", "__context__"):
            next_exc = getattr(current, attr, None)
            if next_exc is not None and next_exc is not current:
                current = next_exc
                break
        else:
            break

    return None


def classify_user_integrity_error(exc: IntegrityError):
    message = str(exc).lower()
    constraint_name = _extract_constraint_name(exc)

    if constraint_name and "username" in constraint_name:
        raise ConflictError("Username already exists")
    if constraint_name and "email" in constraint_name:
        raise ConflictError("Email already exists")
    if "unique" in message and "username" in message:
        raise ConflictError("Username already exists")
    if "unique" in message and "email" in message:
        raise ConflictError("Email already exists")

    raise ValidationError("Invalid user payload")


def classify_url_integrity_error(exc: IntegrityError):
    message = str(exc).lower()
    constraint_name = _extract_constraint_name(exc)

    if constraint_name and "short_code" in constraint_name:
        raise ConflictError("short_code already exists")
    if "unique" in message and "short_code" in message:
        raise ConflictError("short_code already exists")
    if "foreign key" in message or (constraint_name and "user" in constraint_name):
        raise ValidationError("user_id does not reference an existing user")

    raise ValidationError("Invalid URL payload")


def classify_event_integrity_error(exc: IntegrityError):
    message = str(exc).lower()
    if "foreign key" in message:
        raise ValidationError("url_id and user_id must reference existing records")
    raise ValidationError("Invalid event payload")
