"""
Centralized logging configuration with PII redaction.

All modules should use:
    from agent.logging_config import get_logger
    logger = get_logger(__name__)

The PII filter automatically masks sensitive data (TC Kimlik, DOB)
before it reaches log output — even if a developer accidentally logs it.
"""

import logging
import re
import sys


class PIIRedactionFilter(logging.Filter):
    """Intercepts log records and masks personal data before output."""

    PATTERNS = [
        # TC Kimlik: 11 consecutive digits (standalone)
        (re.compile(r'\b(\d{3})\d{5}(\d{3})\b'), r'\1****\2'),
        # Date of birth patterns: DD/MM/YYYY, DD.MM.YYYY, DD-MM-YYYY
        (re.compile(r'\b(\d{2})[/.\-](\d{2})[/.\-](\d{4})\b'), r'**/**/\3'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            record.args = tuple(
                self._redact(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True

    def _redact(self, text: str) -> str:
        for pattern, replacement in self.PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def get_logger(name: str) -> logging.Logger:
    """Get a logger with PII redaction filter attached.

    Args:
        name: Module name, typically __name__.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        pii_filter = PIIRedactionFilter()

        # Console handler
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        console.addFilter(pii_filter)
        logger.addHandler(console)

        # File handler
        file_handler = logging.FileHandler("data/agent.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(pii_filter)
        logger.addHandler(file_handler)

        logger.setLevel(logging.INFO)

    return logger
