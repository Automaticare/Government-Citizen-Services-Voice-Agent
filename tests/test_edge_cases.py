"""
Tests for edge case handling — auth format variations, date parsing,
partial TC Kimlik extraction.
"""

import pytest
from agent.tools.tc_kimlik import (
    validate_tc_kimlik, normalize_tc_input, extract_partial_tc, mask_tc_kimlik,
)
from agent.tools.date_parser import normalize_date


class TestNormalizeTcInput:
    """Test TC Kimlik input normalization from voice."""

    def test_clean_digits(self):
        assert normalize_tc_input("12345678901") == "12345678901"

    def test_spaces(self):
        assert normalize_tc_input("123 456 789 01") == "12345678901"

    def test_dashes(self):
        assert normalize_tc_input("123-456-789-01") == "12345678901"

    def test_mixed_separators(self):
        assert normalize_tc_input("123 456-789 01") == "12345678901"

    def test_with_text(self):
        assert normalize_tc_input("TC numaram 12345678901") == "12345678901"

    def test_with_turkish_text(self):
        assert normalize_tc_input("numaram 123 45 678 90 1 dir") == "12345678901"


class TestExtractPartialTc:
    """Test partial TC Kimlik extraction from voice."""

    def test_full_number(self):
        from api.seed_data import generate_valid_tc
        tc = generate_valid_tc("100000001")
        digits, hint = extract_partial_tc(tc)
        assert hint == "full"
        assert digits == tc

    def test_last_digits(self):
        digits, hint = extract_partial_tc("sonu 901 ile biten")
        assert hint == "last_digits"
        assert digits == "901"

    def test_son_hanesi(self):
        digits, hint = extract_partial_tc("son 4567")
        assert hint == "last_digits"
        assert digits == "4567"

    def test_first_digits(self):
        digits, hint = extract_partial_tc("ilk 123")
        assert hint == "first_digits"
        assert digits == "123"

    def test_partial_digits(self):
        digits, hint = extract_partial_tc("12345")
        assert hint == "partial"
        assert digits == "12345"

    def test_no_digits(self):
        digits, hint = extract_partial_tc("bilmiyorum")
        assert hint == "none"
        assert digits is None


class TestDateNormalization:
    """Test date parsing from various voice input formats."""

    def test_slash_format(self):
        date, err = normalize_date("15/03/1990")
        assert date == "15/03/1990"
        assert err == ""

    def test_dot_format(self):
        date, err = normalize_date("15.03.1990")
        assert date == "15/03/1990"

    def test_dash_format(self):
        date, err = normalize_date("15-03-1990")
        assert date == "15/03/1990"

    def test_turkish_month_name(self):
        date, err = normalize_date("15 Mart 1990")
        assert date == "15/03/1990"

    def test_turkish_month_lowercase(self):
        date, err = normalize_date("15 mart 1990")
        assert date == "15/03/1990"

    def test_turkish_month_special_chars(self):
        date, err = normalize_date("15 Şubat 1990")
        assert date == "15/02/1990"

    def test_english_month(self):
        date, err = normalize_date("March 15, 1990")
        assert date == "15/03/1990"

    def test_english_month_no_comma(self):
        date, err = normalize_date("March 15 1990")
        assert date == "15/03/1990"

    def test_reversed_order(self):
        date, err = normalize_date("1990 mart 15")
        assert date == "15/03/1990"

    def test_iso_format(self):
        date, err = normalize_date("1990-03-15")
        assert date == "15/03/1990"

    def test_single_digit_day(self):
        date, err = normalize_date("5/3/1990")
        assert date == "05/03/1990"

    def test_invalid_format(self):
        date, err = normalize_date("on bes mart bin dokuz yuz doksan")
        assert date is None
        assert "anlayamadim" in err.lower()

    def test_all_turkish_months(self):
        months = {
            "ocak": "01", "subat": "02", "mart": "03", "nisan": "04",
            "mayis": "05", "haziran": "06", "temmuz": "07", "agustos": "08",
            "eylul": "09", "ekim": "10", "kasim": "11", "aralik": "12",
        }
        for name, num in months.items():
            date, err = normalize_date(f"1 {name} 2000")
            assert date == f"01/{num}/2000", f"Failed for {name}"
