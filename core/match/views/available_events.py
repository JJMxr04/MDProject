"""``available_events_for_match`` — server-side helper for the pick popup.

Returns the catalog of events a user can pick from for one match's window.
Source-of-truth is the aggregator's ``GET /v1/events``. Two
callers:

- ``my_match_detail_view`` calls ``build_available_events(match)`` to populate
  the JSON island at template line 162.
- A standalone JSON endpoint (URL name ``portal-available-events-for-match``)
  is exposed for HTMX / fetch-based callers.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET

from core import timeprefs
from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
    proxy_logo_url,
)
from core.match.decorators import player_in_match_required
from core.match.models import Match
from core.portal.cards import resolve_matchup_tints

logger = logging.getLogger(__name__)


# Owner-side deadline: pick must be ≥ 8h before event start
# (per Game.objects.upload_pick rules).
OWNER_DEADLINE_BUFFER = timedelta(hours=8)
# Headroom for an event to FINISH and settle before the match window closes.
# The aggregator gives us only a ``start_time`` (no end/duration), so we
# approximate "the event fits inside the match timeframe" as
# ``start_time + EVENT_COMPLETION_BUFFER <= match.end_date``. Without it a
# late-starting event clears the start-time bound but wouldn't settle until
# after the match itself ended — acute on the short Blitz (2-day) window.
EVENT_COMPLETION_BUFFER = timedelta(hours=6)
CACHE_TTL = 30  # seconds


def _shape_for_popup(item: dict) -> dict:
    """Tiny adapter — popup JS uses ``event_id`` everywhere; aggregator's
    schema field is ``id``. Add the alias; rewrite team logos to MDProject's
    same-origin proxy endpoint at the source (the popup renders client-side,
    so a relative ``/logos/teams/{id}`` resolves against MDProject's origin —
    which is exactly where we now serve them); and resolve the matchup tints
    from each team's primary_color so the JS only applies the values.
    """
    home = dict(item.get("home_team") or {})
    away = dict(item.get("away_team") or {})
    if home:
        home["logo_url"] = proxy_logo_url(home.get("logo_url"))
    if away:
        away["logo_url"] = proxy_logo_url(away.get("logo_url"))
    home_tint, away_tint = resolve_matchup_tints(
        home.get("primary_color"), away.get("primary_color")
    )
    out = {**item, "event_id": item["id"]}
    if home:
        out["home_team"] = home
    if away:
        out["away_team"] = away
    out["home_tint"] = home_tint
    out["away_tint"] = away_tint
    return out


def _with_display_time(item: dict) -> dict:
    """Add ``start_time_display`` — the start time pre-formatted in the viewing
    user's timezone + clock format (backend is authoritative; the popup JS
    inserts the string verbatim instead of localizing). Applied per request,
    NEVER cached, so the cross-user events cache can't bleed one user's zone
    into another's (cached fragments).
    """
    iso = item.get("start_time")
    dt = parse_datetime(iso) if isinstance(iso, str) else iso
    return {**item, "start_time_display": timeprefs.format_datetime(dt, "datetime")}


def build_available_events(match: Match) -> list[dict]:
    """Returns the list of event dicts the popup hydrates from."""
    if not match.end_date:
        return []

    cache_key = f"portal:events:match:{match.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return [_with_display_time(it) for it in cached]

    starts_after_dt = timezone.now() + OWNER_DEADLINE_BUFFER
    # Pull the upper bound in so a pick can still finish + settle inside the
    # match's format window (Blitz 2d / Classic 4d / Marathon 7d — end_date is
    # derived from the format at creation/accept).
    starts_before_dt = match.end_date - EVENT_COMPLETION_BUFFER

    # Window effectively closed: nothing can start late enough to clear the
    # owner deadline yet early enough to settle before the match ends.
    if starts_before_dt <= starts_after_dt:
        return []

    starts_after = starts_after_dt.isoformat()
    starts_before = starts_before_dt.isoformat()

    try:
        body = AggrigatorClient().list_events(
            starts_after=starts_after,
            starts_before=starts_before,
            page_size=200,
        )
    except AggrigatorError as exc:
        logger.warning(
            "aggregator unreachable for match=%s available_events: %s",
            match.id, exc,
        )
        return []

    items = [_shape_for_popup(it) for it in (body.get("items") or [])]
    cache.set(cache_key, items, timeout=CACHE_TTL)
    # Display strings are added on return (not stored) — see _with_display_time.
    return [_with_display_time(it) for it in items]


@require_GET
@login_required(login_url="/auth/login/")
@player_in_match_required
def available_events_for_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    return JsonResponse({"items": build_available_events(match)})
