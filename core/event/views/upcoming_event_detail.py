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
from core.portal.cards import fixture_from_dict
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
    is_finalized = bool(body.get("is_finalized"))

    # Analytics block — H2H, form, season-to-date PLUS the model-vs-market
    # edge table. Phase 16 (D-16d) made the analytics dashboard FREE — the
    # block renders for everyone (the model-vs-market edge degrades gracefully
    # to empty while the model is parked). PRO gating now lives on opponent
    # scouting (Phase 9), not here.
    is_entitled = True
    analytics_ctx: dict = {}
    if is_entitled:
        # Shared catalog data — the client's service key covers auth
        # (plan §6.4); no per-user provisioning needed anymore.
        context = analytics_client.event_context(event_id)
        historical_stats = analytics_client.event_historical_stats(event_id)
        analytics_ctx = {
            "form_into_match": context.get("form_into_match") or {},
            "form_detail": context.get("form_detail") or {},
            "h2h_last_5": context.get("h2h_last_5") or [],
            "h2h_aggregate": context.get("h2h_aggregate") or {},
            "historical_stats": historical_stats or {},
        }
        # Model-vs-market is upcoming-only — past events render historical
        # stats instead, which is already in analytics_ctx above.
        if not is_finalized:
            model_prob = analytics_client.event_probabilities(event_id)
            live_odds = analytics_client.event_live_odds(event_id)
            analytics_ctx.update({
                "model_prob": model_prob or {},
                "live_odds": live_odds,
                "edge_rows": _build_edge_rows(model_prob, live_odds),
            })

    # Shared matchup cluster (same component as duels / upcoming list).
    # Built from the RAW aggregator dict so logos are absolutized and the
    # team primary_color tints apply (the _EventAdapter is kept for the
    # markets / analytics sections below).
    fixture = fixture_from_dict(body)

    # Hero win-probability bars. Soccer-only: the model returns probabilities
    # only for sports with a parked-or-live model, so this is None elsewhere
    # and the template hides the bars.
    win_prob = _win_prob(analytics_ctx.get("model_prob"))

    # Tab visibility — only render the Odds / Analytics tabs when there is
    # something in them (the page degrades to just Overview otherwise).
    has_odds = bool(markets)
    has_analytics = _has_analytics(analytics_ctx)

    ctx = {
        "event": event_view,
        "fixture": fixture,
        "win_prob": win_prob,
        "has_odds": has_odds,
        "has_analytics": has_analytics,
        # Raw aggregator dict — used by ``{% humanize_pick_payload %}``
        # so the template can render plain-English selection labels
        # without us having to maintain dict-or-attribute fallbacks
        # inside humanize.py.
        "event_raw": body,
        "markets": markets,
        "served_stale": served_stale,
        "is_entitled_to_analytics": is_entitled,
        "is_past": is_finalized,
    }
    ctx.update(analytics_ctx)
    return render(request, "portal/event/upcoming_event_detail.html", ctx)


def _win_prob(model_prob: dict | None) -> dict | None:
    """Hero win-probability bars from the model's home/away probabilities.

    Returns ``None`` when no model probability is available (e.g. non-soccer
    events, where the template hides the bars). The draw probability is folded
    away — the bars are a two-sided home-vs-away split.
    """
    if not model_prob or model_prob.get("p_home") is None:
        return None
    p_home = model_prob.get("p_home")
    p_away = model_prob.get("p_away")
    return {
        "p_home": p_home,
        "p_away": p_away,
        "home_pct": round((p_home or 0) * 100),
        "away_pct": round((p_away or 0) * 100),
    }


def _has_analytics(analytics_ctx: dict) -> bool:
    """Whether the Analytics tab has any populated section to show."""
    h2h = analytics_ctx.get("h2h_aggregate") or {}
    form = analytics_ctx.get("form_detail") or {}
    hist = analytics_ctx.get("historical_stats") or {}
    return bool(
        h2h.get("played")
        or analytics_ctx.get("h2h_last_5")
        or form.get("home") or form.get("away")
        or hist.get("home") or hist.get("away")
        or analytics_ctx.get("edge_rows")
    )


def _build_edge_rows(model_prob: dict | None, live_odds: dict | None) -> list[dict]:
    """Model-vs-market edge rows for the inline analytics card.

    Mirrors the helper that used to live in
    ``core/portal/views/analytics.py``. Returns an empty list whenever
    we don't have both model and live-odds moneyline data — the
    template treats that as the empty-state path.
    """
    if not model_prob or model_prob.get("p_home") is None:
        return []
    if not live_odds:
        return []
    ml_markets = [
        m for m in (live_odds.get("markets") or [])
        if m.get("market_type") == "moneyline"
    ]
    if not ml_markets:
        return []
    ml = ml_markets[0]
    vig_adj = ml.get("vig_adjusted_implied") or {}
    best_by_side = {bp.get("side"): bp for bp in (ml.get("best_prices") or [])}
    model_by_side = {
        "home": model_prob.get("p_home"),
        "draw": model_prob.get("p_draw"),
        "away": model_prob.get("p_away"),
    }
    rows: list[dict] = []
    for side in ("home", "draw", "away"):
        market_p = vig_adj.get(side)
        model_p = model_by_side.get(side)
        if market_p is None or model_p is None:
            continue
        bp = best_by_side.get(side)
        rows.append({
            "side": side,
            "model_prob": model_p,
            "market_prob": market_p,
            "edge_pp": (model_p - market_p) * 100.0,
            "best_decimal": bp.get("decimal_odds") if bp else None,
            "best_bookmaker": bp.get("bookmaker_name") if bp else None,
            "best_deeplink": bp.get("deeplink") if bp else None,
        })
    return rows


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
            self.team_id = None
            return
        self.name = (
            team.get("name_long") or team.get("name_medium") or team.get("name_short")
        )
        # Plain string so ``{{ team.logo_url }}`` and ``{% if team.logo_url %}``
        # both work — matches the _team_logo.html partial contract and the
        # legacy Team model's .logo_url property. Rewrite the aggregator logo
        # URL to MDProject's same-origin proxy so the browser never calls the
        # key-gated aggregator directly (see proxy_logo_url).
        from core.event.providers.aggregator_client import proxy_logo_url

        self.logo_url = proxy_logo_url(team.get("logo_url")) or None
        # ``team_id`` is the fallback display when ``name`` is blank —
        # several analytics partials do ``team.name|default:team.team_id``.
        # Aggregator payload may carry it as ``id`` or ``team_id`` depending
        # on shape; check both.
        self.team_id = team.get("team_id") or team.get("id") or ""


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
            Event.objects.select_related(
                "home_team", "home_team__logo",
                "away_team", "away_team__logo",
                "sport",
            ),
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
        {
            "event": event, "markets": markets, "win_prob": None,
            "has_odds": bool(markets), "has_analytics": False,
        },
    )
