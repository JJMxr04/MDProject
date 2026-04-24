"""Odds format conversion helpers.

Internal source of truth is decimal (float, 4 dp in DB). American and fractional
are derived on demand for API responses.
"""

from decimal import Decimal
from fractions import Fraction


def fractional_to_decimal(value: str) -> Decimal:
    """`"13/10"` -> `Decimal("2.3000")`. Also accepts `"evens"` or `"1/1"`."""
    s = (value or "").strip().lower()
    if s in ("", "evens", "even", "1/1"):
        return Decimal("2.0000")
    try:
        num_str, den_str = s.split("/")
        frac = Fraction(int(num_str), int(den_str))
    except (ValueError, ZeroDivisionError):
        return Decimal("1.0000")
    return (Decimal(frac.numerator) / Decimal(frac.denominator) + Decimal(1)).quantize(
        Decimal("0.0001")
    )


def decimal_to_american(decimal_odds) -> int:
    d = Decimal(decimal_odds)
    if d <= Decimal("1.0"):
        return 0
    if d >= Decimal("2.0"):
        return int(((d - Decimal(1)) * 100).to_integral_value(rounding="ROUND_HALF_UP"))
    return int((Decimal(-100) / (d - Decimal(1))).to_integral_value(rounding="ROUND_HALF_UP"))


def decimal_to_fractional(decimal_odds) -> str:
    """Best-effort low-denominator fraction, capped at denominator 1000."""
    d = Decimal(decimal_odds)
    if d <= Decimal("1.0"):
        return "0/1"
    frac = Fraction(d - Decimal(1)).limit_denominator(1000)
    return f"{frac.numerator}/{frac.denominator}"


def movement_label(change: int) -> str:
    if change > 0:
        return "up"
    if change < 0:
        return "down"
    return "flat"
