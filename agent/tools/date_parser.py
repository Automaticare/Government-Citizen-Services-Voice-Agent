"""
Date parser for voice input.

Handles the many ways Turkish callers say dates:
- "15/03/1990" (standard format)
- "15.03.1990" (dot format)
- "15-03-1990" (dash format)
- "15 Mart 1990" (Turkish month name)
- "March 15, 1990" (English month name)
- "bin dokuz yüz doksan" (spoken year — handled by STT)
- "1990 mart 15" (reversed order)

All outputs normalized to DD/MM/YYYY for database matching.
"""

import re

TURKISH_MONTHS = {
    "ocak": "01", "subat": "02", "şubat": "02", "mart": "03",
    "nisan": "04", "mayis": "05", "mayıs": "05", "haziran": "06",
    "temmuz": "07", "agustos": "08", "ağustos": "08", "eylul": "09",
    "eylül": "09", "ekim": "10", "kasim": "11", "kasım": "11",
    "aralik": "12", "aralık": "12",
}

ENGLISH_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

ALL_MONTHS = {**TURKISH_MONTHS, **ENGLISH_MONTHS}


def normalize_date(raw_input: str) -> tuple[str | None, str]:
    """Parse a date from voice input into DD/MM/YYYY format.

    Args:
        raw_input: Date as spoken or transcribed by STT.

    Returns:
        Tuple of (normalized_date or None, error_message).
        If successful, error_message is empty.
    """
    text = raw_input.strip().lower()

    # Strip ordinal suffixes: 15th → 15, 1st → 1, 2nd → 2, 3rd → 3
    text = re.sub(r'(\d+)(st|nd|rd|th)\b', r'\1', text)

    # Pattern 1: DD/MM/YYYY or DD.MM.YYYY or DD-MM-YYYY
    numeric_match = re.match(r'(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})', text)
    if numeric_match:
        day, month, year = numeric_match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}", ""

    # Pattern 2: "15 Mart 1990" or "15 mart 1990"
    named_match = re.match(r'(\d{1,2})\s+(\w+)\s+(\d{4})', text)
    if named_match:
        day, month_name, year = named_match.groups()
        month_num = ALL_MONTHS.get(month_name)
        if month_num:
            return f"{int(day):02d}/{month_num}/{year}", ""

    # Pattern 3: "March 15, 1990" or "March 15 1990"
    en_match = re.match(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', text)
    if en_match:
        month_name, day, year = en_match.groups()
        month_num = ALL_MONTHS.get(month_name)
        if month_num:
            return f"{int(day):02d}/{month_num}/{year}", ""

    # Pattern 4: "1990 mart 15" (reversed)
    rev_match = re.match(r'(\d{4})\s+(\w+)\s+(\d{1,2})', text)
    if rev_match:
        year, month_name, day = rev_match.groups()
        month_num = ALL_MONTHS.get(month_name)
        if month_num:
            return f"{int(day):02d}/{month_num}/{year}", ""

    # Pattern 5: YYYY-MM-DD (ISO format)
    iso_match = re.match(r'(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})', text)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{int(day):02d}/{int(month):02d}/{year}", ""

    return None, f"Tarih formatini anlayamadim. Lutfen gun/ay/yil olarak soyleyin (ornek: 15/03/1990)"
