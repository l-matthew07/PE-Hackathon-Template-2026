"""Unit tests for logging configuration."""

import logging

from app.logging_config import MemoryLogHandler, RequestIdFilter


class TestMemoryLogHandler:
    def test_stores_entries(self):
        handler = MemoryLogHandler(capacity=10)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello", args=(), exc_info=None,
        )
        record.request_id = "-"
        handler.emit(record)
        entries = handler.get_entries()
        assert len(entries) == 1
        assert entries[0]["message"] == "hello"
        assert entries[0]["level"] == "INFO"

    def test_capacity_limit(self):
        handler = MemoryLogHandler(capacity=3)
        for i in range(5):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=f"msg{i}", args=(), exc_info=None,
            )
            record.request_id = "-"
            handler.emit(record)
        entries = handler.get_entries()
        assert len(entries) == 3
        assert entries[0]["message"] == "msg2"

    def test_filter_by_level(self):
        handler = MemoryLogHandler(capacity=10)
        for level in (logging.INFO, logging.WARNING, logging.ERROR):
            record = logging.LogRecord(
                name="test", level=level, pathname="", lineno=0,
                msg="test", args=(), exc_info=None,
            )
            record.request_id = "-"
            handler.emit(record)
        assert len(handler.get_entries(level="ERROR")) == 1
        assert len(handler.get_entries(level="INFO")) == 1

    def test_limit_parameter(self):
        handler = MemoryLogHandler(capacity=10)
        for i in range(5):
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg=f"msg{i}", args=(), exc_info=None,
            )
            record.request_id = "-"
            handler.emit(record)
        entries = handler.get_entries(limit=2)
        assert len(entries) == 2

    def test_format_time(self):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        ts = MemoryLogHandler.format_time(record)
        assert "T" in ts  # ISO format


class TestRequestIdFilter:
    def test_adds_request_id_outside_context(self):
        filt = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test", args=(), exc_info=None,
        )
        result = filt.filter(record)
        assert result is True
        assert record.request_id == "-"
