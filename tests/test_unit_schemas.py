"""Unit tests for validation / schema parsing functions."""

import pytest

from app.services.errors import ValidationError
from app.services.schemas import (
    parse_event_create,
    parse_shorten_payload,
    parse_url_create,
    parse_url_update,
    parse_user_create,
    parse_user_update,
)


# ── parse_shorten_payload ─────────────────────────────────────────────

class TestParseShortenPayload:
    def test_valid_url(self):
        result = parse_shorten_payload({"url": "https://example.com"})
        assert result.original_url == "https://example.com"

    def test_valid_original_url_field(self):
        result = parse_shorten_payload({"original_url": "http://example.com/path"})
        assert result.original_url == "http://example.com/path"

    def test_with_title(self):
        result = parse_shorten_payload({"url": "https://example.com", "title": "Example"})
        assert result.title == "Example"

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            parse_shorten_payload({})

    def test_empty_url_raises(self):
        with pytest.raises(ValidationError):
            parse_shorten_payload({"url": ""})

    def test_invalid_scheme_raises(self):
        with pytest.raises(ValidationError):
            parse_shorten_payload({"url": "ftp://files.example.com"})

    def test_no_host_raises(self):
        with pytest.raises(ValidationError):
            parse_shorten_payload({"url": "http://"})

    def test_plain_text_raises(self):
        with pytest.raises(ValidationError):
            parse_shorten_payload({"url": "not a url"})

    def test_whitespace_stripped(self):
        result = parse_shorten_payload({"url": "  https://example.com  "})
        assert result.original_url == "https://example.com"


# ── parse_user_create ─────────────────────────────────────────────────

class TestParseUserCreate:
    def test_valid(self):
        result = parse_user_create({"username": "alice", "email": "alice@example.com"})
        assert result.username == "alice"
        assert result.email == "alice@example.com"

    def test_missing_username(self):
        with pytest.raises(ValidationError):
            parse_user_create({"email": "a@b.com"})

    def test_missing_email(self):
        with pytest.raises(ValidationError):
            parse_user_create({"username": "alice"})

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            parse_user_create({"username": "alice", "email": "not-an-email"})

    def test_empty_both(self):
        with pytest.raises(ValidationError):
            parse_user_create({})


# ── parse_user_update ─────────────────────────────────────────────────

class TestParseUserUpdate:
    def test_update_username(self):
        result = parse_user_update({"username": "bob"})
        assert result.username == "bob"

    def test_update_email(self):
        result = parse_user_update({"email": "bob@example.com"})
        assert result.email == "bob@example.com"

    def test_empty_payload_raises(self):
        with pytest.raises(ValidationError):
            parse_user_update({})

    def test_empty_username_raises(self):
        with pytest.raises(ValidationError):
            parse_user_update({"username": ""})

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            parse_user_update({"email": "bad"})


# ── parse_url_create ─────────────────────────────────────────────────

class TestParseUrlCreate:
    def test_valid(self):
        result = parse_url_create({"original_url": "https://example.com"})
        assert result.original_url == "https://example.com"

    def test_missing_url_raises(self):
        with pytest.raises(ValidationError):
            parse_url_create({})

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationError):
            parse_url_create({"original_url": "not-a-url"})

    def test_short_code_too_long_raises(self):
        with pytest.raises(ValidationError):
            parse_url_create({"original_url": "https://example.com", "short_code": "a" * 13})

    def test_short_code_non_alnum_raises(self):
        with pytest.raises(ValidationError):
            parse_url_create({"original_url": "https://example.com", "short_code": "ab-cd"})

    def test_valid_short_code(self):
        result = parse_url_create({"original_url": "https://example.com", "short_code": "abc123"})
        assert result.short_code == "abc123"


# ── parse_url_update ─────────────────────────────────────────────────

class TestParseUrlUpdate:
    def test_update_title(self):
        result = parse_url_update({"title": "New Title"})
        assert result.title == "New Title"

    def test_update_is_active(self):
        result = parse_url_update({"is_active": False})
        assert result.is_active is False

    def test_empty_raises(self):
        with pytest.raises(ValidationError):
            parse_url_update({})

    def test_invalid_url_raises(self):
        with pytest.raises(ValidationError):
            parse_url_update({"original_url": "bad"})

    def test_empty_url_raises(self):
        with pytest.raises(ValidationError):
            parse_url_update({"original_url": ""})


# ── parse_event_create ────────────────────────────────────────────────

class TestParseEventCreate:
    def test_valid(self):
        result = parse_event_create({
            "url_id": 1,
            "user_id": 1,
            "event_type": "click",
            "timestamp": "2024-01-01T00:00:00Z",
        })
        assert result.event_type == "click"
        assert result.url_id == 1

    def test_missing_event_type_raises(self):
        with pytest.raises(ValidationError):
            parse_event_create({"url_id": 1, "user_id": 1})

    def test_missing_url_id_raises(self):
        with pytest.raises(ValidationError):
            parse_event_create({"user_id": 1, "event_type": "click"})

    def test_invalid_timestamp_raises(self):
        with pytest.raises(ValidationError):
            parse_event_create({
                "url_id": 1,
                "user_id": 1,
                "event_type": "click",
                "timestamp": "not-a-date",
            })

    def test_details_string_raises(self):
        with pytest.raises(ValidationError):
            parse_event_create({
                "url_id": 1,
                "user_id": 1,
                "event_type": "click",
                "details": "not-an-object",
            })

    def test_details_object_is_accepted(self):
        result = parse_event_create({
            "url_id": 1,
            "user_id": 1,
            "event_type": "click",
            "details": {"referrer": "https://example.com"},
        })
        assert result.details is not None
