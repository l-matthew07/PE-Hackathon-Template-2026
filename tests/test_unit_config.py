"""Unit tests for configuration."""

import os

from app.config import _env_int


class TestEnvInt:
    def test_valid_int(self):
        os.environ["_TEST_INT"] = "42"
        assert _env_int("_TEST_INT", 0) == 42
        del os.environ["_TEST_INT"]

    def test_missing_returns_default(self):
        assert _env_int("_NONEXISTENT_VAR", 99) == 99

    def test_invalid_returns_default(self):
        os.environ["_TEST_INT"] = "not_a_number"
        assert _env_int("_TEST_INT", 7) == 7
        del os.environ["_TEST_INT"]

    def test_empty_returns_default(self):
        os.environ["_TEST_INT"] = ""
        assert _env_int("_TEST_INT", 5) == 5
        del os.environ["_TEST_INT"]
