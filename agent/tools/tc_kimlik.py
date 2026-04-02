"""
TC Kimlik (Turkish National ID) validation.

Validates the 11-digit TC Kimlik number using the official
checksum algorithm. This is a deterministic utility — not an
LLM tool. Called before DB lookup to reject obviously invalid numbers.

Algorithm:
  - First digit cannot be 0
  - d10 = ((d1+d3+d5+d7+d9) * 7 - (d2+d4+d6+d8)) % 10
  - d11 = (d1+d2+d3+d4+d5+d6+d7+d8+d9+d10) % 10
"""


def validate_tc_kimlik(tc_kimlik: str) -> tuple[bool, str]:
    """Validate a TC Kimlik number format and checksum.

    Args:
        tc_kimlik: The TC Kimlik string (may contain spaces).

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is empty.
    """
    # Strip whitespace and non-digit chars (voice input may have spaces)
    cleaned = "".join(c for c in tc_kimlik if c.isdigit())

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
    cleaned = "".join(c for c in tc_kimlik if c.isdigit())
    if len(cleaned) != 11:
        return "***INVALID***"
    return f"{cleaned[:3]}****{cleaned[8:]}"
