"""Unit tests for service helper methods."""

from datetime import datetime

from app.services.urls_service import UrlsService
from app.services.users_service import UsersService
from app.services.events_service import EventsService


class TestUrlsServiceHelpers:
    def test_parse_optional_int_none(self):
        assert UrlsService._parse_optional_int(None) is None

    def test_parse_optional_int_empty(self):
        assert UrlsService._parse_optional_int("") is None

    def test_parse_optional_int_valid(self):
        assert UrlsService._parse_optional_int("42") == 42

    def test_parse_optional_int_invalid(self):
        assert UrlsService._parse_optional_int("abc") is None

    def test_parse_datetime_none(self):
        assert UrlsService._parse_datetime(None) is None

    def test_parse_datetime_empty(self):
        assert UrlsService._parse_datetime("") is None

    def test_parse_datetime_valid(self):
        result = UrlsService._parse_datetime("2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_parse_datetime_invalid(self):
        assert UrlsService._parse_datetime("not-a-date") is None

    def test_parse_bool_true(self):
        assert UrlsService._parse_bool("true") is True
        assert UrlsService._parse_bool(True) is True

    def test_parse_bool_false(self):
        assert UrlsService._parse_bool("false") is False
        assert UrlsService._parse_bool("0") is False


class TestUsersServiceHelpers:
    def test_parse_optional_int(self):
        assert UsersService._parse_optional_int(None) is None
        assert UsersService._parse_optional_int("") is None
        assert UsersService._parse_optional_int("5") == 5
        assert UsersService._parse_optional_int("abc") is None

    def test_parse_created_at(self):
        assert UsersService._parse_created_at(None) is None
        assert UsersService._parse_created_at("") is None
        result = UsersService._parse_created_at("2024-06-01T00:00:00Z")
        assert isinstance(result, datetime)
        assert UsersService._parse_created_at("bad") is None


class TestEventsServiceHelpers:
    def test_parse_required_int(self):
        assert EventsService._parse_required_int(None) is None
        assert EventsService._parse_required_int("") is None
        assert EventsService._parse_required_int("10") == 10
        assert EventsService._parse_required_int("abc") is None

    def test_parse_timestamp(self):
        assert EventsService._parse_timestamp(None) is None
        assert EventsService._parse_timestamp("") is None
        result = EventsService._parse_timestamp("2024-01-01T00:00:00Z")
        assert isinstance(result, datetime)
        assert EventsService._parse_timestamp("bad") is None
