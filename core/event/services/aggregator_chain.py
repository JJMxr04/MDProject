"""``ensure_chain_from_aggregator(event_id, selection_id)`` — get-or-create
the full ``Sport → League → Team → Event → Market → Selection`` chain for a
selection the user just picked.

Per plan §2.4.3. Called by ``upload_pick`` / ``player_2_select_outcome`` *before*
``Game.objects.upload_pick`` so the local DB has the rows that legacy code
``Selection.objects.get(pk=selection_id)`` expects.

The aggregator is the source of truth for odds — the client's submitted
``selection_id`` is the lookup key, but every column we write comes from the
aggregator response. Never trust the client's payload for odds values.

Field-naming note (post plan v2 portal redesign): the aggregator's Pydantic
schemas expose ``id`` as the primary key on every entity (Market.id,
Selection.id, Team.id) — *not* ``market_id`` / ``selection_id`` like the legacy
DRF serializers did. This module reads the canonical ``id`` field.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from dateutil import parser as date_parser
from django.conf import settings
from django.db import transaction

from core.event.models import (
    Event,
    League,
    Market,
    Selection,
    Sport,
    Team,
)
from core.event.models.odds.bookmaker import Bookmaker, BookmakerSelection
from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)

logger = logging.getLogger(__name__)


class ChainBuildError(Exception):
    """Raised when the aggregator can't supply enough data to build the chain."""


def ensure_chain(event_id: str, selection_id: str) -> Selection:
    """Fetch the chain from the aggregator and ``get_or_create`` it locally.

    Returns the local ``Selection`` row. Raises ``ChainBuildError`` if the
    aggregator is unreachable or the selection isn't found in the response.

    Idempotent — re-calling with the same ``(event_id, selection_id)`` after
    the chain exists is just a series of get-or-create no-ops.
    """
    if not getattr(settings, "USE_AGGRIGATOR", False):
        # Pre-cutover: the local DB is the catalog; no chain build needed.
        # If the row is missing, the existing ``Selection.objects.get(pk=...)``
        # in Game.objects.upload_pick will raise the right error.
        try:
            return Selection.objects.get(pk=selection_id)
        except Selection.DoesNotExist:
            raise ChainBuildError(f"Selection {selection_id} not in local DB")

    try:
        # ``get_event(include_markets=True)`` returns a flat ``EventDetailOut``
        # (event fields at top level + ``markets`` array). Single round-trip
        # gives us everything the chain needs.
        body = AggrigatorClient().get_event(event_id, include_markets=True)
    except AggrigatorError as exc:
        raise ChainBuildError(f"Aggregator unavailable: {exc}") from exc
    if not body:
        raise ChainBuildError(f"Event {event_id} not found in aggregator")

    chosen, parent_market = _find_selection(body, selection_id=selection_id)
    if chosen is None or parent_market is None:
        raise ChainBuildError(
            f"Selection {selection_id} not found for event {event_id}"
        )

    with transaction.atomic():
        sport = _upsert_sport(body)
        league = _upsert_league(body, sport)
        home_team = _upsert_team(body.get("home_team"), league)
        away_team = _upsert_team(body.get("away_team"), league)
        event = _upsert_event(
            body, sport=sport, league=league,
            home=home_team, away=away_team,
        )
        market = _upsert_market(parent_market, event=event, sport=sport)
        selection = _upsert_selection(chosen, market=market)
        # Per-book quotes — display-only data the popup uses to show
        # "DraftKings -150 / FanDuel -145" and the deeplinks.
        _upsert_book_quotes(selection, chosen.get("by_bookmaker") or [])
    return selection


# ---- finders ---------------------------------------------------------------


def _find_selection(
    body: dict, *, selection_id: str,
) -> tuple[dict | None, dict | None]:
    """Search the aggregator's ``EventDetailOut`` response for the chosen
    selection. Returns ``(selection_dict, parent_market_dict)``.
    """
    for market in body.get("markets") or []:
        for sel in market.get("selections") or []:
            if sel.get("id") == selection_id:
                return sel, market
    return None, None


# ---- upserts (per plan §2.4.3 chain order) -------------------------------


def _upsert_sport(event_env: dict) -> Sport | None:
    sport_id = event_env.get("sport_id")
    if not sport_id:
        return None
    nested = event_env.get("sport") or {}
    obj, _ = Sport.objects.get_or_create(
        id=sport_id,
        defaults={"name": nested.get("name") or sport_id.title()},
    )
    return obj


def _upsert_league(event_env: dict, sport: Sport | None) -> League | None:
    league_id = event_env.get("league_id")
    if not league_id or sport is None:
        return None
    nested = event_env.get("league") or {}
    obj, _ = League.objects.get_or_create(
        id=league_id,
        defaults={"sport": sport, "name": nested.get("name") or league_id},
    )
    return obj


def _upsert_team(team_env: dict | None, league: League | None) -> Team | None:
    if not team_env or league is None:
        return None
    raw_team_id = team_env.get("team_id")
    if not raw_team_id:
        return None
    pk = team_env.get("id") or f"{league.id}:{raw_team_id}"
    obj, _ = Team.objects.get_or_create(
        id=pk,
        defaults={
            "league": league,
            "team_id": raw_team_id,
            "sport": league.sport,
            "name_long": (team_env.get("name_long") or raw_team_id)[:128],
            "name_medium": (team_env.get("name_medium") or raw_team_id)[:64],
            "name_short": (team_env.get("name_short") or raw_team_id)[:32],
            "primary_color": team_env.get("primary_color"),
            "stat_entity_id": (team_env.get("stat_entity_id") or "")[:8],
        },
    )
    return obj


def _upsert_event(
    event_env: dict, *,
    sport: Sport | None, league: League | None,
    home: Team | None, away: Team | None,
) -> Event:
    # update_or_create (not get_or_create): the aggregator is the source of
    # truth, and the local mirror can hold a stale lifecycle (e.g. a
    # finished event re-listed as upcoming after a sim reseed). A stale
    # ``finished`` status freezes the game card (is_settled) even though
    # the event hasn't kicked off. Same convention as
    # ``Event.objects.upsert_from_spec`` on the ingest path.
    defaults = {
        "sport": sport,
        "league": league,
        "home_team": home,
        "away_team": away,
        "type": (event_env.get("type") or "")[:16],
        "season_label": (event_env.get("season_label") or "")[:64],
        "start_time": _iso(event_env.get("start_time")),
        "status_type": (event_env.get("status_type") or "")[:32],
        "status_display": (event_env.get("status_display") or "")[:64],
        "current_period_id": (event_env.get("current_period_id") or "")[:16],
        "is_live": bool(event_env.get("is_live")),
        "is_finalized": bool(event_env.get("is_finalized")),
        "completed": bool(event_env.get("completed")),
        "home_score": event_env.get("home_score"),
        "away_score": event_env.get("away_score"),
        "winner_code": event_env.get("winner_code"),
        "feed_locked": bool(event_env.get("feed_locked")),
    }
    # A payload missing sport/league must not null out a previously resolved
    # value — Markets copy ``event.sport_id`` into a NOT NULL column.
    if sport is None:
        defaults.pop("sport")
    if league is None:
        defaults.pop("league")
    obj, _ = Event.objects.update_or_create(id=event_env["id"], defaults=defaults)
    return obj


def _upsert_market(market_env: dict, *, event: Event, sport: Sport | None) -> Market:
    sport_id = sport.id if sport else event.sport_id
    if sport_id is None:
        # ``Market.sport`` is NOT NULL — fail with the chain's designed error
        # instead of an opaque IntegrityError mid-transaction.
        raise ChainBuildError(
            f"No sport resolvable for market {market_env['id']} "
            f"(event {event.id})"
        )
    obj, _ = Market.objects.update_or_create(
        id=market_env["id"],
        defaults={
            "event": event,
            "sport_id": sport_id,
            "category": market_env.get("category", ""),
            "type": (market_env.get("type") or "")[:64],
            "scope": market_env.get("scope", "FULL_GAME"),
            "line": _decimal(market_env.get("line")),
            "side": market_env.get("side", ""),
            "provider": "sportsgameodds",
            "provider_market_id": market_env.get("provider_market_id") or "",
            "provider_choice_group": "",
            "subject_team_id": market_env.get("subject_team_id"),
            "is_live": bool(market_env.get("is_live")),
            "suspended": bool(market_env.get("suspended")),
            "last_updated": _iso(market_env.get("last_updated")) or event.last_provider_refresh_at or _now(),
        },
    )
    return obj


def _upsert_selection(sel_env: dict, *, market: Market) -> Selection:
    # Refreshed on every pick — odds_at_pick is copied from this row at
    # bet time, so a stale mirror would freeze outdated odds into the bet.
    obj, _ = Selection.objects.update_or_create(
        id=sel_env["id"],
        defaults={
            "market": market,
            "type": sel_env.get("type", ""),
            "label": (sel_env.get("label") or "")[:128],
            "decimal_odds": _decimal(sel_env.get("decimal_odds")),
            "opening_decimal_odds": _decimal(sel_env.get("opening_decimal_odds")),
            "movement": int(sel_env.get("movement") or 0),
            "settlement_status": sel_env.get("settlement_status") or "PENDING",
            "settlement_source": sel_env.get("settlement_source") or "",
            "settled_at": _iso(sel_env.get("settled_at")),
        },
    )
    return obj


def _upsert_book_quotes(selection: Selection, books: list[dict]) -> None:
    """Mirror the aggregator's ``by_bookmaker`` payload into local
    ``Bookmaker`` + ``BookmakerSelection`` rows.

    Idempotent: ``update_or_create`` on ``(selection, bookmaker)`` so re-picking
    the same selection refreshes the quotes instead of duplicating rows."""
    for b in books:
        book_id = b.get("bookmaker_id")
        if not book_id:
            continue
        bookmaker, _ = Bookmaker.objects.get_or_create(
            id=book_id,
            defaults={"name": (b.get("bookmaker_name") or book_id)[:64]},
        )
        BookmakerSelection.objects.update_or_create(
            selection=selection, bookmaker=bookmaker,
            defaults={
                "decimal_odds": _decimal(b.get("decimal_odds")),
                "spread": _decimal(b.get("spread")),
                "over_under": _decimal(b.get("over_under")),
                "available": bool(b.get("available", True)),
                "deeplink": (b.get("deeplink") or "")[:500],
                "last_updated_at": _iso(b.get("last_updated_at")),
            },
        )


# ---- type helpers ---------------------------------------------------------


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _iso(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None


def _now():
    from django.utils import timezone
    return timezone.now()
