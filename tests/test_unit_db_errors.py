"""Unit tests for database error classification."""

import pytest
from peewee import IntegrityError

from app.services.db_errors import (
    classify_event_integrity_error,
    classify_url_integrity_error,
    classify_user_integrity_error,
)
from app.services.errors import ConflictError, ValidationError


class TestClassifyUserIntegrityError:
    def test_username_unique_constraint(self):
        exc = IntegrityError("UNIQUE constraint failed: user.username")
        with pytest.raises(ConflictError, match="Username already exists"):
            classify_user_integrity_error(exc)

    def test_email_unique_constraint(self):
        exc = IntegrityError("UNIQUE constraint failed: user.email")
        with pytest.raises(ConflictError, match="Email already exists"):
            classify_user_integrity_error(exc)

    def test_generic_error(self):
        exc = IntegrityError("something else")
        with pytest.raises(ValidationError, match="Invalid user payload"):
            classify_user_integrity_error(exc)


class TestClassifyUrlIntegrityError:
    def test_short_code_unique(self):
        exc = IntegrityError("UNIQUE constraint failed: url.short_code")
        with pytest.raises(ConflictError, match="short_code already exists"):
            classify_url_integrity_error(exc)

    def test_original_url_unique_message(self):
        exc = IntegrityError("UNIQUE constraint failed: url.original_url")
        with pytest.raises(ConflictError, match="original_url already exists"):
            classify_url_integrity_error(exc)

    def test_original_url_unique_constraint_name(self):
        class _Diag:
            constraint_name = "url_original_url_key"

        exc = IntegrityError("duplicate key value violates unique constraint")
        exc.diag = _Diag()
        with pytest.raises(ConflictError, match="original_url already exists"):
            classify_url_integrity_error(exc)

    def test_foreign_key_error(self):
        exc = IntegrityError("FOREIGN KEY constraint failed")
        with pytest.raises(ValidationError, match="user_id"):
            classify_url_integrity_error(exc)

    def test_generic_error(self):
        exc = IntegrityError("other error")
        with pytest.raises(ValidationError, match="Invalid URL payload"):
            classify_url_integrity_error(exc)


class TestClassifyEventIntegrityError:
    def test_foreign_key_error(self):
        exc = IntegrityError("FOREIGN KEY constraint failed")
        with pytest.raises(ValidationError, match="user_id"):
            classify_event_integrity_error(exc)

    def test_generic_error(self):
        exc = IntegrityError("other")
        with pytest.raises(ValidationError, match="Invalid event payload"):
            classify_event_integrity_error(exc)
