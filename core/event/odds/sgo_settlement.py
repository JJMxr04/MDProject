"""Settlement grader for SportsGameOdds payloads.

PROVIDER source for the existing ``Selection.settlement_status`` enum, fed by
the per-odd ``score`` field SGO ships once ``status.finalized=true``. Grades
are authoritative — they override COMPUTED but not MANUAL.

For ML/SP/ML3WAY the grader needs both sides' scores, so it walks the spec
list rather than per-odd. For OU/YN/EO the per-odd score is sufficient.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.utils import timezone

from core.event.models import Event, Selection

logger = logging.getLogger(__name__)


def grade_event(event: Event, market_specs: Iterable) -> int:
    """Walk a finalized event's market specs and PROVIDER-grade each selection.

    Returns count of selections graded. Idempotent: re-running on the same
    event leaves WON/LOST rows alone unless the score changed.

    After grading, walks affected Matches and runs ``maybe_complete_match`` —
    the queryset ``.update()`` calls below skip Django's post_save signal so
    the Selection-settled match-completion hook would otherwise never fire.
    """
    if not event.is_finalized:
        return 0
    now = timezone.now()
    graded = 0
    for mspec in market_specs:
        graded += _grade_market(mspec, now)
    if graded:
        logger.info("PROVIDER-graded %d selections on event=%s", graded, event.id)
        from core.event.odds.settlement import propagate_to_matches

        propagate_to_matches(event)
    return graded


def _grade_market(mspec, now: datetime) -> int:
    """Dispatch by category. Mutates ``Selection`` rows on the matching market."""
    if mspec.category == "MONEYLINE":
        return _grade_moneyline(mspec, now)
    if mspec.category == "SPREAD":
        return _grade_spread(mspec, now)
    if mspec.category in ("TOTAL", "PROPS_TEAM"):
        return _grade_totals(mspec, now)
    if mspec.category == "PROPS_GAME":
        return _grade_props_game(mspec, now)
    return 0


def _grade_moneyline(mspec, now) -> int:
    by_side = {sel.raw_side_id: sel for sel in mspec.selections}
    home, away, draw = by_side.get("home"), by_side.get("away"), by_side.get("draw")
    if home is None or away is None:
        return 0
    h_score, a_score = home.score, away.score
    if h_score is None or a_score is None:
        return 0
    if h_score > a_score:
        return _apply([(home, "WON"), (away, "LOST"), (draw, "LOST")], now)
    if a_score > h_score:
        return _apply([(home, "LOST"), (away, "WON"), (draw, "LOST")], now)
    return _apply([(home, "LOST"), (away, "LOST"), (draw, "WON" if draw else None)], now)


def _grade_spread(mspec, now) -> int:
    by_side = {sel.raw_side_id: sel for sel in mspec.selections}
    home, away = by_side.get("home"), by_side.get("away")
    if home is None or away is None or home.score is None or away.score is None:
        return 0
    if mspec.line is None:
        return 0
    margin = home.score - away.score
    adjusted = float(margin) + float(mspec.line)
    if adjusted > 0:
        return _apply([(home, "WON"), (away, "LOST")], now)
    if adjusted < 0:
        return _apply([(home, "LOST"), (away, "WON")], now)
    return _apply([(home, "PUSH"), (away, "PUSH")], now)


def _grade_totals(mspec, now) -> int:
    """OVER/UNDER markets (TOTAL or per-side PROPS_TEAM total)."""
    by_side = {sel.raw_side_id: sel for sel in mspec.selections}
    over, under = by_side.get("over"), by_side.get("under")
    if over is None or under is None:
        return 0
    score = over.score if over.score is not None else under.score
    if score is None or mspec.line is None:
        return 0
    line = float(mspec.line)
    if score > line:
        return _apply([(over, "WON"), (under, "LOST")], now)
    if score < line:
        return _apply([(over, "LOST"), (under, "WON")], now)
    return _apply([(over, "PUSH"), (under, "PUSH")], now)


def _grade_props_game(mspec, now) -> int:
    """yn / eo / etc. — single-odd grading via the score field."""
    graded = 0
    for sel in mspec.selections:
        if sel.score is None:
            continue
        if sel.raw_side_id in ("yes", "no"):
            won = bool(int(sel.score))
            new_status = (
                "WON"
                if (won and sel.raw_side_id == "yes") or (not won and sel.raw_side_id == "no")
                else "LOST"
            )
        elif sel.raw_side_id in ("even", "odd"):
            is_even = int(sel.score) % 2 == 0
            new_status = (
                "WON"
                if (is_even and sel.raw_side_id == "even")
                or ((not is_even) and sel.raw_side_id == "odd")
                else "LOST"
            )
        else:
            continue
        graded += _apply_one(sel, new_status, now)
    return graded


# ---- writers ----------------------------------------------------------------


def _apply(pairs, now: datetime) -> int:
    """Apply a list of (SelectionSpec, status). Skips None entries."""
    graded = 0
    for spec, status in pairs:
        if spec is None or status is None:
            continue
        graded += _apply_one(spec, status, now)
    return graded


def _apply_one(spec, status: str, now: datetime) -> int:
    """Update one Selection row by its synthesized PK. Skips MANUAL rows."""
    n = (
        Selection.objects.filter(id=spec.selection_id)
        .exclude(settlement_source="MANUAL")
        .update(
            settlement_status=status,
            settled_at=now,
            settlement_source="PROVIDER",
        )
    )
    return n
