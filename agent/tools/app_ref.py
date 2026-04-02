"""
Application reference number validation.

Format: YYYY-XX-NNNN (e.g., 2024-TR-0001)
"""

import re

APP_REF_PATTERN = re.compile(r"^\d{4}-[A-Z]{2}-\d{4}$")


def validate_app_ref(app_ref: str) -> tuple[bool, str]:
    """Validate an application reference number format.

    Args:
        app_ref: The reference string (e.g., "2024-TR-0001").

    Returns:
        Tuple of (is_valid, error_message).
    """
    cleaned = app_ref.strip().upper()

    if not APP_REF_PATTERN.match(cleaned):
        return False, "Application reference must be in format YYYY-XX-NNNN (e.g., 2024-TR-0001)"

    return True, ""
