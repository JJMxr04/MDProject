"""``ensure_chain_from_aggregator(event_id, selection_id)`` — get-or-create
the full ``Sport → League → Team → Event → Market → Selection`` chain for a
selection the user just picked.

Per plan §2.4.3. Called by ``upload_pick`` / ``player_2_select_outcome`` *before*
``Game.objects.upload_pick`` so the local DB has the rows that legacy code
``Selection.objects.get(pk=selection_id)`` expects.

The aggregator is the source of truth for odds — the client's submitted
``selection_id`` is the lookup key, but every column we write comes from the
aggregator response. Never trust the client's payload for odds values.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

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
        body = AggrigatorClient().get_event_markets(event_id)
    except AggrigatorError as exc:
        raise ChainBuildError(f"Aggregator unavailable: {exc}") from exc
    if not body:
        raise ChainBuildError(f"Event {event_id} not found in aggregator")

    chosen, parent_market, event_envelope = _find_selection(
        body, selection_id=selection_id, event_id=event_id,
    )
    if chosen is None or parent_market is None:
        raise ChainBuildError(
            f"Selection {selection_id} not found for event {event_id}"
        )

    with transaction.atomic():
        sport = _upsert_sport(event_envelope)
        league = _upsert_league(event_envelope, sport)
        home_team = _upsert_team(event_envelope.get("home_team"), league)
        away_team = _upsert_team(event_envelope.get("away_team"), league)
        event = _upsert_event(
            event_envelope, sport=sport, league=league,
            home=home_team, away=away_team,
        )
        market = _upsert_market(parent_market, event=event, sport=sport)
        selection = _upsert_selection(chosen, market=market)
    return selection


# ---- finders ---------------------------------------------------------------


def _find_selection(
    body: dict, *, selection_id: str, event_id: str,
) -> tuple[dict | None, dict | None, dict]:
    """Search the aggregator's ``GET /v1/events/{id}/markets`` response for
    the chosen selection. Returns ``(selection_dict, parent_market_dict,
    event_envelope)``.

    ``event_envelope`` falls back to a minimal dict synthesized from
    ``event_id`` + the markets' shared ``sport_id`` if the aggregator didn't
    embed an event block in the markets response (defensive — current
    aggregator responses always include it).
    """
    for market in body.get("markets") or []:
        for sel in market.get("selections") or []:
            if sel.get("selection_id") == selection_id:
                return sel, market, body.get("event") or {"event_id": event_id}
    return None, None, body.get("event") or {"event_id": event_id}


# ---- upserts (per plan §2.4.3 chain order) -------------------------------


def _upsert_sport(event_env: dict) -> Sport | None:
    sport_id = event_env.get("sport_id")
    if not sport_id:
        return None
    obj, _ = Sport.objects.get_or_create(
        id=sport_id, defaults={"name": sport_id.title()},
    )
    return obj


def _upsert_league(event_env: dict, sport: Sport | None) -> League | None:
    league_id = event_env.get("league_id")
    if not league_id or sport is None:
        return None
    obj, _ = League.objects.get_or_create(
        id=league_id,
        defaults={"sport": sport, "name": league_id},
    )
    return obj


def _upsert_team(team_env: dict | None, league: League | None) -> Team | None:
    if not team_env or league is None:
        return None
    team_id = team_env.get("team_id")
    if not team_id:
        return None
    pk = f"{league.id}:{team_id}"
    obj, _ = Team.objects.get_or_create(
        id=pk,
        defaults={
            "league": league,
            "team_id": team_id,
            "sport": league.sport,
            "name_long": (team_env.get("name_long") or team_id)[:128],
            "name_medium": (team_env.get("name_medium") or team_id)[:64],
            "name_short": (team_env.get("name_short") or team_id)[:32],
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
    obj, _ = Event.objects.get_or_create(
        id=event_env["event_id"],
        defaults={
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
        },
    )
    return obj


def _upsert_market(market_env: dict, *, event: Event, sport: Sport | None) -> Market:
    obj, _ = Market.objects.get_or_create(
        id=market_env["market_id"],
        defaults={
            "event": event,
            "sport_id": sport.id if sport else event.sport_id,
            "category": market_env.get("category", ""),
            "type": (market_env.get("type") or "")[:64],
            "scope": market_env.get("scope", "FULL_GAME"),
            "line": _decimal(market_env.get("line")),
            "side": market_env.get("side", ""),
            "provider": "sportsgameodds",
            "provider_market_id": "",
            "provider_choice_group": "",
            "subject_team_id": market_env.get("subject_team_id"),
            "is_live": bool(market_env.get("is_live")),
            "suspended": bool(market_env.get("suspended")),
            "last_updated": _iso(market_env.get("last_updated")) or event.last_provider_refresh_at or _now(),
        },
    )
    return obj


def _upsert_selection(sel_env: dict, *, market: Market) -> Selection:
    obj, _ = Selection.objects.get_or_create(
        id=sel_env["selection_id"],
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
