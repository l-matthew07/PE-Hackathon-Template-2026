"""Unit tests for utility functions and service helpers."""

from datetime import datetime

from app.lib.utils import format_datetime, parse_bool
from app.services.errors import (
    ConflictError,
    InternalError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from app.services.shortener_service import ShortenerService


# ── format_datetime ───────────────────────────────────────────────────

class TestFormatDatetime:
    def test_none(self):
        assert format_datetime(None) is None

    def test_datetime_object(self):
        dt = datetime(2024, 1, 15, 12, 30, 0)
        result = format_datetime(dt)
        assert "2024-01-15" in result
        assert "12:30:00" in result

    def test_string_passthrough(self):
        assert format_datetime("some-string") == "some-string"


# ── parse_bool ────────────────────────────────────────────────────────

class TestParseBool:
    def test_true_values(self):
        for val in ("1", "true", "True", "t", "yes", "y", "on"):
            assert parse_bool(val) is True

    def test_false_values(self):
        for val in ("0", "false", "False", "f", "no", "n", "off"):
            assert parse_bool(val) is False

    def test_none_default(self):
        assert parse_bool(None) is False
        assert parse_bool(None, default=True) is True

    def test_bool_passthrough(self):
        assert parse_bool(True) is True
        assert parse_bool(False) is False

    def test_unknown_returns_default(self):
        assert parse_bool("maybe") is False
        assert parse_bool("maybe", default=True) is True


# ── ServiceError hierarchy ────────────────────────────────────────────

class TestServiceErrors:
    def test_validation_error(self):
        err = ValidationError("bad input")
        assert isinstance(err, ServiceError)
        assert err.status == 400
        assert err.code == "VALIDATION_ERROR"

    def test_conflict_error(self):
        err = ConflictError("duplicate")
        assert err.status == 409
        assert err.code == "CONFLICT"

    def test_not_found_error(self):
        err = NotFoundError("missing")
        assert err.status == 404
        assert err.code == "NOT_FOUND"

    def test_internal_error(self):
        err = InternalError("boom")
        assert err.status == 500
        assert err.code == "INTERNAL_ERROR"

    def test_details_preserved(self):
        err = ValidationError("bad", details={"fields": ["url"]})
        assert err.details == {"fields": ["url"]}


# ── ShortenerService._generate_code ──────────────────────────────────

class TestGenerateCode:
    def test_default_length(self):
        code = ShortenerService._generate_code()
        assert len(code) == 8
        assert code.isalnum()

    def test_custom_length(self):
        code = ShortenerService._generate_code(length=10)
        assert len(code) == 10

    def test_codes_are_unique(self):
        codes = {ShortenerService._generate_code() for _ in range(100)}
        assert len(codes) > 90  # probabilistically all unique


# ── ShortenerService._parse_bool ─────────────────────────────────────

class TestShortenerParseBool:
    def test_true_strings(self):
        for val in ("1", "true", "yes", "on"):
            assert ShortenerService._parse_bool(val) is True

    def test_false_strings(self):
        for val in ("0", "false", "no", "off"):
            assert ShortenerService._parse_bool(val) is False

    def test_bool_passthrough(self):
        assert ShortenerService._parse_bool(True) is True
        assert ShortenerService._parse_bool(False) is False
