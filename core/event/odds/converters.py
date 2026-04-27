"""Odds format conversion helpers.

Internal source of truth is decimal (Decimal, 4 dp in DB). American and
fractional are derived on demand for API responses.

Provider input format: SportsGameOdds ships American strings like ``"+130"``
or ``"-150"``. ``american_to_decimal`` is the canonical inbound parser; the
``decimal_to_*`` helpers serve outbound API responses.
"""

from decimal import Decimal
from fractions import Fraction


def american_to_decimal(value) -> Decimal | None:
    """`"+130"` -> `Decimal("2.3000")`; `"-150"` -> `Decimal("1.6667")`.

    Returns ``None`` for empty / unparseable inputs (so callers can skip rather
    than guess). ``"+100"`` and ``"-100"`` both map to ``Decimal("2.0000")``.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        n = int(s)
    except ValueError:
        return None
    if n == 0:
        return None
    if n > 0:
        return (Decimal(n) / Decimal(100) + Decimal(1)).quantize(Decimal("0.0001"))
    # Negative: -100 / n + 1
    return (Decimal(-100) / Decimal(n) + Decimal(1)).quantize(Decimal("0.0001"))


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
