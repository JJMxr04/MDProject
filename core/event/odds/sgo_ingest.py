"""Persist ``MarketSpec`` lists to ``Market`` / ``Selection`` /
``BookmakerSelection`` / ``OddsQuote`` rows.

Pure-spec parsing lives in ``sgo_normalize`` and is unit-testable without a DB.
This file is the side-effecting layer: every call is wrapped in a transaction
and every upsert is keyed on the deterministic IDs that ``sgo_normalize``
produces.
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from core.event.models import (
    Bookmaker,
    BookmakerSelection,
    Event,
    Market,
    OddsQuote,
    Selection,
    Team,
)
from core.event.odds.sgo_normalize import BookmakerQuoteSpec, MarketSpec, SelectionSpec

logger = logging.getLogger(__name__)


@transaction.atomic
def write_markets(event: Event, market_specs: Iterable[MarketSpec]) -> int:
    """Upsert markets/selections/per-book quotes for one event.

    Returns the count of selections written.

    Also kicks off the SGO ``score``-based settlement grader on finalized
    events — see ``core.event.odds.sgo_settlement.grade_event``.
    """
    written = 0
    for mspec in market_specs:
        market = _upsert_market(event, mspec)
        for sspec in mspec.selections:
            sel = _upsert_selection(market, sspec, mspec)
            written += 1
            _maybe_record_quote(sel, sspec)
            _upsert_bookmaker_quotes(sel, sspec.by_bookmaker)

    # Provider-grade newly-final selections from per-odd ``score`` field.
    if event.is_finalized:
        from core.event.odds.sgo_settlement import grade_event

        try:
            grade_event(event, market_specs)
        except Exception:  # noqa: BLE001 — never break ingest on settlement bugs
            logger.exception("sgo_settlement.grade_event failed for event=%s", event.id)

    return written


# --------------------------------------------------------------------- helpers


def _resolve_subject_team(event: Event, side_marker: str) -> Team | None:
    if side_marker == "HOME":
        return event.home_team
    if side_marker == "AWAY":
        return event.away_team
    return None


def _upsert_market(event: Event, spec: MarketSpec) -> Market:
    subject_team = _resolve_subject_team(event, spec.side)
    obj, _ = Market.objects.update_or_create(
        id=spec.market_id,
        defaults=dict(
            event=event,
            sport_id=event.sport_id,
            category=spec.category,
            type=spec.market_type[:64],
            scope=spec.scope,
            line=spec.line,
            side=spec.side,
            provider="sportsgameodds",
            provider_market_id=(spec.provider_market_id or "")[:128],
            provider_choice_group="",
            subject_team=subject_team,
            is_live=spec.is_live,
            suspended=spec.suspended,
            last_updated=spec.last_updated_at,
        ),
    )
    return obj


def _upsert_selection(market: Market, spec: SelectionSpec, mspec: MarketSpec) -> Selection:
    obj, _ = Selection.objects.update_or_create(
        id=spec.selection_id,
        defaults=dict(
            market=market,
            type=spec.selection_type,
            label=spec.label[:128],
            decimal_odds=spec.decimal_odds,
            opening_decimal_odds=spec.opening_decimal_odds,
            movement=_movement(spec),
            suspended=spec.suspended,
        ),
    )
    return obj


def _movement(spec: SelectionSpec) -> int:
    if spec.opening_decimal_odds is None or spec.decimal_odds is None:
        return 0
    if spec.decimal_odds > spec.opening_decimal_odds:
        return 1
    if spec.decimal_odds < spec.opening_decimal_odds:
        return -1
    return 0


def _maybe_record_quote(sel: Selection, spec: SelectionSpec) -> None:
    """One movement row per real price change."""
    if spec.decimal_odds is None:
        return
    last = (
        OddsQuote.objects.filter(selection=sel)
        .order_by("-captured_at")
        .values_list("decimal_odds", flat=True)
        .first()
    )
    if last is not None and last == spec.decimal_odds:
        return
    OddsQuote.objects.get_or_create(
        selection=sel,
        captured_at=timezone.now(),
        defaults={"decimal_odds": spec.decimal_odds},
    )


def _upsert_bookmaker_quotes(
    sel: Selection, books: Iterable[BookmakerQuoteSpec]
) -> None:
    for q in books:
        bookmaker, _ = Bookmaker.objects.get_or_create(
            id=q.bookmaker_id,
            defaults={"name": q.bookmaker_id.title()},
        )
        BookmakerSelection.objects.update_or_create(
            selection=sel,
            bookmaker=bookmaker,
            defaults=dict(
                decimal_odds=q.decimal_odds,
                spread=q.spread,
                over_under=q.over_under,
                available=q.available,
                deeplink=q.deeplink or "",
                last_updated_at=q.last_updated_at or timezone.now(),
            ),
        )
