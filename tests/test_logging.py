"""
Test PII redaction filter and logging configuration.
"""

import logging
from agent.logging_config import PIIRedactionFilter, get_logger


class TestPIIRedactionFilter:
    """Test that sensitive data is masked in log output."""

    def setup_method(self):
        self.filter = PIIRedactionFilter()

    def _make_record(self, msg: str) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="",
            lineno=0, msg=msg, args=None, exc_info=None,
        )
        return record

    def test_tc_kimlik_is_masked(self):
        record = self._make_record("User verified: 12345678901")
        self.filter.filter(record)
        assert record.msg == "User verified: 123****901"

    def test_tc_kimlik_masked_in_turkish_context(self):
        record = self._make_record("TC Kimlik: 98765432109 dogrulandi")
        self.filter.filter(record)
        assert record.msg == "TC Kimlik: 987****109 dogrulandi"

    def test_dob_slash_format_masked(self):
        record = self._make_record("DOB: 15/03/1990")
        self.filter.filter(record)
        assert record.msg == "DOB: **/**/1990"

    def test_dob_dot_format_masked(self):
        record = self._make_record("Dogum tarihi: 01.12.1985")
        self.filter.filter(record)
        assert record.msg == "Dogum tarihi: **/**/1985"

    def test_dob_dash_format_masked(self):
        record = self._make_record("Birth: 25-07-2000")
        self.filter.filter(record)
        assert record.msg == "Birth: **/**/2000"

    def test_non_sensitive_text_unchanged(self):
        record = self._make_record("Agent started session")
        self.filter.filter(record)
        assert record.msg == "Agent started session"

    def test_short_numbers_not_masked(self):
        record = self._make_record("Attempt 3 of 3")
        self.filter.filter(record)
        assert record.msg == "Attempt 3 of 3"

    def test_multiple_pii_in_one_message(self):
        record = self._make_record("ID: 12345678901, DOB: 15/03/1990")
        self.filter.filter(record)
        assert "123****901" in record.msg
        assert "**/**/1990" in record.msg


class TestGetLogger:
    """Test logger factory function."""

    def test_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_has_pii_filter(self):
        logger = get_logger("test.pii_check")
        handler = logger.handlers[0]
        filter_types = [type(f) for f in handler.filters]
        assert PIIRedactionFilter in filter_types
