"""
TC Kimlik (Turkish National ID) validation.

Validates the 11-digit TC Kimlik number using the official
checksum algorithm. This is a deterministic utility — not an
LLM tool. Called before DB lookup to reject obviously invalid numbers.

Handles voice input edge cases:
- Spaces/dashes between digits ("123 456 789 01")
- Turkish word numbers ("bir iki üç" → not handled here, STT does this)
- Partial input ("sonu 901 ile biten") → extract_partial_tc()
- Repeated digits from correction ("hayır hayır, 123..." → cleaned by strip)

Algorithm:
  - First digit cannot be 0
  - d10 = ((d1+d3+d5+d7+d9) * 7 - (d2+d4+d6+d8)) % 10
  - d11 = (d1+d2+d3+d4+d5+d6+d7+d8+d9+d10) % 10
"""

import re


def normalize_tc_input(raw_input: str) -> str:
    """Normalize voice input into a clean digit string.

    Handles various ways callers speak their TC Kimlik:
    - "123 456 789 01" → "12345678901"
    - "123-456-789-01" → "12345678901"
    - "TC'm 12345678901" → "12345678901"
    - "numaram 123 45 678 90 1" → "12345678901"
    """
    return "".join(c for c in raw_input if c.isdigit())


def extract_partial_tc(raw_input: str) -> tuple[str | None, str]:
    """Extract partial TC Kimlik info from voice input.

    Handles cases like:
    - "sonu 901 ile biten" → (last_digits="901", hint="last_3")
    - "ilk üç hanesi 123" → (first_digits="123", hint="first_3")
    - Full number → (full_number, hint="full")

    Returns:
        Tuple of (extracted_digits or None, hint_type).
    """
    text = raw_input.lower()
    digits = normalize_tc_input(raw_input)

    # Full number provided
    if len(digits) == 11:
        return digits, "full"

    # "sonu X ile biten" or "son X hanesi"
    last_match = re.search(r'son[u]?\s*(\d{2,4})', text)
    if last_match:
        return last_match.group(1), "last_digits"

    # "ilk X hanesi" or "başı X"
    first_match = re.search(r'(?:ilk|bas[iı])\s*(\d{2,4})', text)
    if first_match:
        return first_match.group(1), "first_digits"

    # Just digits but not 11
    if digits and len(digits) != 11:
        return digits, "partial"

    return None, "none"


def validate_tc_kimlik(tc_kimlik: str) -> tuple[bool, str]:
    """Validate a TC Kimlik number format and checksum.

    Args:
        tc_kimlik: The TC Kimlik string (may contain spaces, dashes, etc).

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty.
    """
    cleaned = normalize_tc_input(tc_kimlik)

    if len(cleaned) != 11:
        return False, f"TC Kimlik must be 11 digits, got {len(cleaned)}"

    if cleaned[0] == "0":
        return False, "TC Kimlik cannot start with 0"

    digits = [int(d) for d in cleaned]

    # Checksum validation
    odd_sum = sum(digits[i] for i in range(0, 9, 2))   # d1,d3,d5,d7,d9
    even_sum = sum(digits[i] for i in range(1, 8, 2))   # d2,d4,d6,d8

    expected_d10 = (odd_sum * 7 - even_sum) % 10
    if digits[9] != expected_d10:
        return False, "Invalid TC Kimlik (checksum failed)"

    expected_d11 = sum(digits[:10]) % 10
    if digits[10] != expected_d11:
        return False, "Invalid TC Kimlik (checksum failed)"

    return True, ""


def mask_tc_kimlik(tc_kimlik: str) -> str:
    """Mask a TC Kimlik for safe logging/display.

    Example: "12345678901" → "123****901"
    """
    cleaned = normalize_tc_input(tc_kimlik)
    if len(cleaned) != 11:
        return "***INVALID***"
    return f"{cleaned[:3]}****{cleaned[8:]}"
