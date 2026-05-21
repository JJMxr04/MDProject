"""Upcoming-event detail page, server-rendered.

After the aggregator cutover (plan §2.4.2 / §7.4), this view proxies to
``GET /v1/events/{id}?include=markets`` instead of reading the local DB.
Mirrors the failure modes of ``upcoming_events_list``:

- Aggregator 5xx / timeout → serve cached snapshot if present (TTL extended
  to 5 min in that case), otherwise show an error empty-state.
- Aggregator 404 → Django 404.
- ``USE_AGGRIGATOR=False`` (rollback path): fall back to the legacy local-DB
  query unchanged, so flipping the env flag back is a clean revert.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)
from core.portal.services import aggrigator_client as analytics_client

logger = logging.getLogger(__name__)


CACHE_TTL_OK = 60       # seconds — fresh aggregator data
CACHE_TTL_STALE = 300   # seconds — extended on aggregator failure
SPORTS_LEAGUES_TTL = 300  # name lookups change rarely


@login_required(login_url="/auth/login/")
def upcoming_event_detail(request, event_id):
    if event_id is None:
        logger.error("Received None as event_id.")
        return HttpResponseNotFound("Invalid event ID")

    if not getattr(settings, "USE_AGGRIGATOR", False):
        return _legacy_local_db_path(request, event_id)

    body, served_stale = _fetch_or_cached(event_id)
    if body is None:
        # Aggregator 404 → real not-found. Distinguishable from the empty
        # tuple ``(None, False)`` returned only when both fresh fetch and
        # cache miss after a transport error (handled below).
        not_found = cache.get(_cache_key(event_id, kind="404"))
        if not_found:
            return HttpResponseNotFound("Event not found")
        return render(
            request,
            "portal/event/upcoming_event_detail.html",
            {"event": None, "markets": [], "aggregator_error": True},
            status=503,
        )

    sport_names = _name_index("portal:sports:dropdown", _fetch_sports)
    league_names = _name_index("portal:leagues:dropdown", _fetch_leagues)

    event_view = _EventAdapter(body, sport_names, league_names)
    markets = body.get("markets") or []

    # Past-analytics surface: H2H + per-team form charts + per-team
    # season-to-date stats. Fetched best-effort — if the analytics
    # endpoints are unreachable (no tenant key, network blip, sport
    # without a model) the empty dicts collapse to empty-state markup
    # in the template rather than blocking the markets render.
    tenant_key = getattr(request.user, "aggrigator_api_key", None) or None
    context = analytics_client.event_context(event_id, tenant_key=tenant_key)
    historical_stats = analytics_client.event_historical_stats(
        event_id, tenant_key=tenant_key,
    )

    return render(
        request,
        "portal/event/upcoming_event_detail.html",
        {
            "event": event_view,
            # Raw aggregator dict — used by ``{% humanize_pick_payload %}``
            # so the template can render plain-English selection labels
            # without us having to maintain dict-or-attribute fallbacks
            # inside humanize.py.
            "event_raw": body,
            "markets": markets,
            "served_stale": served_stale,
            "form_into_match": context.get("form_into_match") or {},
            "form_detail": context.get("form_detail") or {},
            "h2h_last_5": context.get("h2h_last_5") or [],
            "h2h_aggregate": context.get("h2h_aggregate") or {},
            "historical_stats": historical_stats or {},
        },
    )


# ---- aggregator fetch / cache -------------------------------------------


def _cache_key(event_id: str, *, kind: str = "body") -> str:
    return f"portal:event:detail:{kind}:{event_id}"


def _fetch_or_cached(event_id: str) -> tuple[dict | None, bool]:
    """Returns ``(body, served_stale)``.

    ``body`` is the aggregator's event payload (with markets) on success or
    cache hit; ``None`` on aggregator 404 *or* on transport error with no
    cached snapshot. Callers distinguish between those by checking the
    ``"404"`` cache marker.
    """
    body_key = _cache_key(event_id)
    cached = cache.get(body_key)
    client = AggrigatorClient()
    try:
        body = client.get_event(event_id, include_markets=True)
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for event=%s detail: %s", event_id, exc)
        if cached is not None:
            cache.set(body_key, cached, timeout=CACHE_TTL_STALE)
            return cached, True
        return None, False

    if body is None:
        # Real 404 from aggregator. Memoize briefly so refresh-spamming a
        # bad URL doesn't hammer the upstream.
        cache.set(_cache_key(event_id, kind="404"), True, timeout=CACHE_TTL_OK)
        return None, False

    cache.set(body_key, body, timeout=CACHE_TTL_OK)
    return body, False


def _name_index(cache_key: str, loader) -> dict[str, str]:
    """Load a ``{id: name}`` lookup from cache, refreshing via ``loader`` on miss."""
    cached = cache.get(cache_key)
    if cached is not None:
        return _to_index(cached)
    try:
        items = loader()
    except AggrigatorError:
        items = []
    cache.set(cache_key, items, timeout=SPORTS_LEAGUES_TTL)
    return _to_index(items)


def _to_index(items: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items or []:
        ident = it.get("id")
        name = it.get("name") or it.get("name_long") or ident
        if ident:
            out[ident] = name
    return out


def _fetch_sports() -> list[dict]:
    return AggrigatorClient().get_sports()


def _fetch_leagues() -> list[dict]:
    return AggrigatorClient().get_leagues()


# ---- adapters: aggregator dict → template-friendly objects ---------------


class _LogoUrlBox:
    """Mirrors Django's ImageFieldFile so ``{{ team.logo_url.url }}`` works
    on aggregator data and ``{% if team.logo_url %}`` falsy-checks correctly
    when the URL is blank.
    """

    def __init__(self, url: str):
        self.url = url

    def __bool__(self) -> bool:
        return bool(self.url)


class _NamedRef:
    """Stand-in for sport/league objects whose only template usage is ``.name``."""

    def __init__(self, name: str):
        self.name = name

    def __bool__(self) -> bool:
        return bool(self.name)


class _TeamAdapter:
    def __init__(self, team: dict | None):
        if team is None:
            self.name = None
            self.logo_url = None
            return
        # Template uses ``team.name`` and ``team.logo_url.url`` — wire those
        # to the aggregator's wider ``name_long`` and bare URL string.
        self.name = (
            team.get("name_long") or team.get("name_medium") or team.get("name_short")
        )
        url = team.get("logo_url")
        self.logo_url = _LogoUrlBox(url) if url else None


class _EventAdapter:
    """Template-shaped wrapper around an aggregator event payload."""

    def __init__(
        self,
        body: dict,
        sport_names: dict[str, str],
        league_names: dict[str, str],
    ):
        self.id = body.get("id")
        self.season_label = body.get("season_label")
        self.start_time = _to_datetime(body.get("start_time"))
        self.status_type = body.get("status_type")
        self.status_display = body.get("status_display")
        self.home_score = body.get("home_score")
        self.away_score = body.get("away_score")
        self.winner_code = body.get("winner_code")
        self.is_live = bool(body.get("is_live"))
        self.is_finalized = bool(body.get("is_finalized"))
        self.completed = bool(body.get("completed"))
        self.home_team = _TeamAdapter(body.get("home_team"))
        self.away_team = _TeamAdapter(body.get("away_team"))
        sport_id = body.get("sport_id")
        league_id = body.get("league_id")
        # Prefer the nested ``sport``/``league`` objects from the enriched
        # response (plan v2); fall back to the dropdown-name lookup for older
        # responses that didn't ship them inline.
        nested_sport = body.get("sport") or {}
        nested_league = body.get("league") or {}
        sport_name = nested_sport.get("name") or sport_names.get(sport_id, "")
        league_name = nested_league.get("name") or league_names.get(league_id, "")
        self.sport = _NamedRef(sport_name) if sport_id else None
        self.league = _NamedRef(league_name) if league_id else None


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime) or value is None:
        return value
    if isinstance(value, str):
        return parse_datetime(value)
    return None


# ---- legacy fallback (rollback path) -------------------------------------


def _legacy_local_db_path(request, event_id):
    """Pre-cutover behavior — keep working when ``USE_AGGRIGATOR=False``."""
    from core.event.models import Event
    from core.event.serializers.event import EventWithMarketsSerializer

    try:
        event = get_object_or_404(
            Event.objects.select_related("home_team", "away_team", "sport"),
            pk=event_id,
        )
    except ValueError:
        return HttpResponseNotFound("Invalid event ID")

    try:
        serialized = EventWithMarketsSerializer(event).data
        markets = serialized.get("markets", []) or []
    except Exception:
        logger.exception("Error serializing markets for event %s", event_id)
        markets = []

    return render(
        request,
        "portal/event/upcoming_event_detail.html",
        {"event": event, "markets": markets},
    )
