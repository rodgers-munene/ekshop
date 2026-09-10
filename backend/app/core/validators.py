"""Input normalisation for user-supplied names, phone numbers and shop names.

Registration accepted almost anything before this: the fields were plain
`str` with no constraints, so scraped-email bot signups landed in the users
table with random-string names and non-Kenyan phone numbers, and genuine
sellers stored their phone in whatever shape they typed it (`0712...`,
`254712...`, `+254 712...`, and at least one `2540712...` produced by
concatenating a country code onto a number that already had its leading 0).
"""

import re

# Deliberately permissive about which letters, strict about everything else:
# apostrophes and hyphens are common in Kenyan names (Murang'a, Wan-Jiru) and
# periods appear in initials, but digits, URLs and punctuation soup are not
# names. No cleverness beyond that -- heuristics that try to detect "gibberish"
# reject real names.
_NAME_EXTRAS = set(" '-.")

# Shop names legitimately carry digits and trading punctuation ("Duka 254",
# "M&K Stores, Nyeri"), so they get their own, wider rule.
_SHOP_NAME_EXTRAS = set(" '-.,&()/")

MAX_NAME_LENGTH = 50
MAX_SHOP_NAME_LENGTH = 60


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def clean_person_name(value: str, field_label: str) -> str:
    """Trim and validate a first/last name, returning the cleaned value."""
    cleaned = _collapse_whitespace(value or "")

    if len(cleaned) < 2:
        raise ValueError(f"{field_label} must be at least 2 characters")
    if len(cleaned) > MAX_NAME_LENGTH:
        raise ValueError(f"{field_label} must be at most {MAX_NAME_LENGTH} characters")
    if not cleaned[0].isalpha():
        raise ValueError(f"{field_label} must start with a letter")
    if not all(c.isalpha() or c in _NAME_EXTRAS for c in cleaned):
        raise ValueError(
            f"{field_label} can only contain letters, spaces, hyphens and apostrophes"
        )

    return cleaned


def clean_shop_name(value: str) -> str:
    """Trim and validate a shop name, returning the cleaned value."""
    cleaned = _collapse_whitespace(value or "")

    if len(cleaned) < 2:
        raise ValueError("Shop name must be at least 2 characters")
    if len(cleaned) > MAX_SHOP_NAME_LENGTH:
        raise ValueError(f"Shop name must be at most {MAX_SHOP_NAME_LENGTH} characters")
    if not any(c.isalpha() for c in cleaned):
        raise ValueError("Shop name must contain at least one letter")
    if not all(c.isalnum() or c in _SHOP_NAME_EXTRAS for c in cleaned):
        raise ValueError("Shop name contains characters that aren't allowed")

    return cleaned


def normalize_phone(value: str) -> str:
    """Normalise a Kenyan mobile number to `2547XXXXXXXX` / `2541XXXXXXXX`.

    Accepts the shapes people actually type -- `0712345678`, `712345678`,
    `+254 712 345 678`, `254-712-345-678` -- and rejects anything that isn't a
    Safaricom/Airtel/Telkom-shaped mobile line, since that's what M-Pesa STK
    push and delivery SMS both need.
    """
    digits = re.sub(r"\D", "", value or "")

    if digits.startswith("254"):
        digits = digits[3:]
    # A leading 0 here is either a local number (0712...) or a country code
    # glued onto one that already had its 0 (2540712...). Both drop the 0.
    if digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 9 or digits[0] not in "17":
        raise ValueError("Enter a valid Kenyan mobile number, e.g. 0712 345 678")

    return f"254{digits}"
