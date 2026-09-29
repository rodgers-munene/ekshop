"""Decimal helpers for money stored as strings.

Money columns in this schema are String(20), so every read comes back as str and
every calculation has to go through Decimal. Arithmetic on the raw column values
silently does the wrong thing: int * str is string repetition, not
multiplication, and "100.00" formatted with ":.2f" raises TypeError.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CENTS = Decimal("0.01")


def to_decimal(value, default: str = "0.00") -> Decimal:
    """Coerce a possibly-None, possibly-corrupt money column to Decimal."""
    if value is None or value == "":
        value = default
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(default)


def quantize(value) -> Decimal:
    """Round to 2dp half-up, the rounding KRA eTIMS requires per line."""
    # + Decimal("0.00") normalises -0.00 to 0.00
    return to_decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP) + CENTS * 0


def multiply(unit_price, quantity) -> Decimal:
    """Line total for a quantity at a unit price. Decimal, not string repetition."""
    return quantize(to_decimal(unit_price) * Decimal(int(quantity)))


def format_kes(value) -> str:
    """Render a money column as 'KES 1,234.50'. Returns 'KES 0.00' on bad data."""
    return f"KES {quantize(value):,.2f}"


def format_kes_plain(value) -> str:
    """Same as format_kes without thousands separators, for fixed-width receipts."""
    return f"KES {quantize(value):.2f}"
