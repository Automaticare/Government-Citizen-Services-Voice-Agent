"""
Tests for TC Kimlik validation and masking.
"""

from agent.tools.tc_kimlik import validate_tc_kimlik, mask_tc_kimlik


class TestValidateTcKimlik:
    """Test TC Kimlik checksum validation."""

    def test_valid_tc_kimlik(self):
        # 10000000146 is a known valid TC Kimlik (Atatürk's)
        is_valid, error = validate_tc_kimlik("10000000146")
        assert is_valid, f"Expected valid but got: {error}"

    def test_starts_with_zero(self):
        is_valid, error = validate_tc_kimlik("01234567890")
        assert not is_valid
        assert "cannot start with 0" in error

    def test_too_short(self):
        is_valid, error = validate_tc_kimlik("1234567890")
        assert not is_valid
        assert "11 digits" in error

    def test_too_long(self):
        is_valid, error = validate_tc_kimlik("123456789012")
        assert not is_valid
        assert "11 digits" in error

    def test_invalid_checksum(self):
        is_valid, error = validate_tc_kimlik("12345678901")
        assert not is_valid
        assert "checksum" in error

    def test_strips_whitespace(self):
        is_valid, _ = validate_tc_kimlik("100 0000 0146")
        assert is_valid

    def test_strips_dashes(self):
        is_valid, _ = validate_tc_kimlik("100-0000-0146")
        assert is_valid

    def test_empty_string(self):
        is_valid, error = validate_tc_kimlik("")
        assert not is_valid
        assert "11 digits" in error

    def test_non_numeric(self):
        is_valid, error = validate_tc_kimlik("abcdefghijk")
        assert not is_valid
        assert "11 digits" in error

    def test_another_valid_number(self):
        # Generate a valid TC Kimlik programmatically
        digits = [1, 0, 0, 0, 0, 0, 0, 0, 0]
        odd_sum = sum(digits[i] for i in range(0, 9, 2))
        even_sum = sum(digits[i] for i in range(1, 8, 2))
        d10 = (odd_sum * 7 - even_sum) % 10
        d11 = (sum(digits) + d10) % 10
        digits.extend([d10, d11])
        tc = "".join(str(d) for d in digits)
        is_valid, error = validate_tc_kimlik(tc)
        assert is_valid, f"Generated TC should be valid: {tc}, error: {error}"


class TestMaskTcKimlik:
    """Test TC Kimlik masking for logs."""

    def test_mask_valid(self):
        assert mask_tc_kimlik("10000000146") == "100****146"

    def test_mask_invalid_length(self):
        assert mask_tc_kimlik("12345") == "***INVALID***"

    def test_mask_with_spaces(self):
        assert mask_tc_kimlik("100 0000 0146") == "100****146"
