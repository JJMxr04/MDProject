"""Portal analytics views — score-driven explore + decision dashboard.

Default landing is the league browser (Explore), per
``plans/analytics/dashboard_and_data/01-information-architecture.md``.
The previous Tonight / Edge dashboard assumed months of stored
bookmaker odds; that data source is gone (see plan 00-overview.md).

Pages in this module:
- ``analytics_landing``      → league card grid (default landing)
- ``analytics_league``       → fixtures + standings for one league
- ``analytics_team``         → team form, H2H, season stats
- ``analytics_event``        → single-event detail (Phase B placeholder)
- ``analytics_upcoming``     → next-24h list (Phase C placeholder)
- ``analytics_picks``        → +EV pick filter (Phase C placeholder)
- ``analytics_bets``         → bet log (Phase D placeholder)

Views degrade gracefully when the aggrigator is unreachable — the
client returns empty shapes and the templates render empty-state cards.
"""

from __future__ import annotations

from django.shortcuts import render

from core.billing.decorators import require_paid
from core.portal.services import aggrigator_client


def _tenant_key(request) -> str | None:
    return request.user.aggrigator_api_key or None


@require_paid
def analytics_landing(request):
    payload = aggrigator_client.list_leagues(tenant_key=_tenant_key(request))
    ctx = {
        "leagues": payload.get("leagues", []),
        "active_tab": "explore",
        "crumbs": [{"label": "Analytics"}],
    }
    return render(request, "portal/analytics/landing.html", ctx)


@require_paid
def analytics_league(request, league_id: str):
    season = request.GET.get("season") or ""
    tab = request.GET.get("tab", "fixtures")
    if tab not in ("fixtures", "standings"):
        tab = "fixtures"

    key = _tenant_key(request)
    fixtures = aggrigator_client.league_fixtures(league_id, season=season, tenant_key=key)
    standings = aggrigator_client.league_standings(league_id, season=season, tenant_key=key)

    # Pick the effective season — prefer the URL value, fall back to
    # whatever the fixtures payload resolved to (the aggrigator answers
    # with the latest available season when none is supplied).
    season_label = (
        season
        or fixtures.get("season_label")
        or standings.get("season_label")
        or ""
    )
    seasons_available = fixtures.get("seasons_available") or standings.get(
        "seasons_available"
    ) or ([season_label] if season_label else [])

    league_name = (
        fixtures.get("league_name")
        or standings.get("league_name")
        or league_id
    )

    ctx = {
        "league_id": league_id,
        "league_name": league_name,
        "season_label": season_label,
        "seasons_available": seasons_available,
        "tab": tab,
        "fixtures": fixtures.get("fixtures", []),
        "standings": standings.get("standings", []),
        "computed_from_events": standings.get("computed_from_events"),
        "expected_events": standings.get("expected_events"),
        "active_tab": "explore",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": league_name},
        ],
    }
    return render(request, "portal/analytics/league.html", ctx)


@require_paid
def analytics_team(request, team_id: str):
    season = request.GET.get("season") or ""
    payload = aggrigator_client.team_summary(
        team_id, season=season, tenant_key=_tenant_key(request),
    )
    team = payload.get("team") or {}
    league_id = team.get("league_id") or ""
    league_label = team.get("league_name") or league_id or "League"
    team_name = team.get("name_long") or team.get("canonical_name") or team_id

    crumbs = [{"label": "Analytics", "href": "/web/portal/analytics/"}]
    if league_id:
        crumbs.append({
            "label": league_label,
            "href": f"/web/portal/analytics/league/{league_id}/",
        })
    crumbs.append({"label": team_name})

    ctx = {
        "team_id": team_id,
        "team": team,
        "season_label": payload.get("season_label") or season,
        "season_stats": payload.get("season_stats") or {},
        "form_last_10": payload.get("form_last_10") or [],
        "home_away_split": payload.get("home_away_split") or {},
        "h2h_recent": payload.get("h2h_recent") or [],
        "elo": payload.get("elo"),
        "has_data": bool(payload.get("season_stats") or payload.get("form_last_10")),
        "active_tab": "explore",
        "crumbs": crumbs,
    }
    return render(request, "portal/analytics/team.html", ctx)


@require_paid
def analytics_event(request, event_id: str):
    """Event detail. Past events render score + post-hoc model + form + H2H;
    future events also render the live-odds card + per-side edge."""
    key = _tenant_key(request)
    event = aggrigator_client.event_detail(event_id)
    model_prob = aggrigator_client.event_probabilities(event_id, tenant_key=key)
    context = aggrigator_client.event_context(event_id, tenant_key=key)

    is_finalized = bool(event.get("is_finalized")) if event else False
    live_odds = None
    edge_rows: list[dict] = []
    if not is_finalized and event:
        live_odds = aggrigator_client.event_live_odds(event_id, tenant_key=key)
        edge_rows = _build_edge_rows(model_prob, live_odds)

    league_id = event.get("league_id") if event else None
    crumbs = [{"label": "Analytics", "href": "/web/portal/analytics/"}]
    if league_id:
        crumbs.append({
            "label": league_id,
            "href": f"/web/portal/analytics/league/{league_id}/",
        })
    crumbs.append({"label": f"Event {event_id}"})

    ctx = {
        "event_id": event_id,
        "event": event,
        "is_past": is_finalized,
        "model_prob": model_prob,
        "form_into_match": context.get("form_into_match") or {},
        "h2h_last_5": context.get("h2h_last_5") or [],
        "live_odds": live_odds,
        "edge_rows": edge_rows,
        "active_tab": "explore",
        "crumbs": crumbs,
    }
    return render(request, "portal/analytics/event.html", ctx)


def _build_edge_rows(model_prob: dict, live_odds: dict) -> list[dict]:
    """Build per-side edge rows for the model-vs-market table.

    Each row carries the model prob, the vig-adjusted market prob,
    the signed edge in percentage points, and the best price for that
    side. Returns ``[]`` when either input is missing the data we need
    so the template can render the live-odds-empty path instead."""
    if not model_prob or model_prob.get("p_home") is None:
        return []
    if not live_odds:
        return []
    ml_markets = [m for m in (live_odds.get("markets") or []) if m.get("market_type") == "moneyline"]
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


_WINDOW_OPTIONS = (
    (24, "Next 24h"),
    (72, "Next 72h"),
    (168, "Next 7 days"),
)


def _parse_window(raw: str | None, default: int = 72) -> int:
    try:
        h = int(raw) if raw else default
    except ValueError:
        return default
    return h if 1 <= h <= 168 else default


def _league_options(tenant_key: str | None) -> list[dict]:
    """Pull the league catalog for the filter dropdown. Empty list if
    the aggrigator is unreachable."""
    payload = aggrigator_client.list_leagues(tenant_key=tenant_key)
    return payload.get("leagues") or []


@require_paid
def analytics_upcoming(request):
    """Upcoming events list — model probability + live-odds badge per row."""
    key = _tenant_key(request)
    league = request.GET.get("league") or None
    hours_ahead = _parse_window(request.GET.get("hours_ahead"))
    payload = aggrigator_client.events_today(
        league=league, hours_ahead=hours_ahead, tenant_key=key,
    )
    ctx = {
        "events": payload.get("events", []),
        "window_from": payload.get("from"),
        "window_to": payload.get("to"),
        "selected_league": league or "",
        "selected_hours": hours_ahead,
        "league_options": _league_options(key),
        "window_options": _WINDOW_OPTIONS,
        "active_tab": "upcoming",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "Upcoming"},
        ],
    }
    return render(request, "portal/analytics/upcoming.html", ctx)


@require_paid
def analytics_picks(request):
    """+EV picks — same data as Upcoming, filtered by best_edge ≥ threshold."""
    key = _tenant_key(request)
    league = request.GET.get("league") or None
    hours_ahead = _parse_window(request.GET.get("hours_ahead"))
    try:
        threshold_pp = float(request.GET.get("threshold_pp") or 3.0)
    except ValueError:
        threshold_pp = 3.0
    payload = aggrigator_client.picks(
        threshold_pp=threshold_pp, league=league,
        hours_ahead=hours_ahead, tenant_key=key,
    )
    ctx = {
        "events": payload.get("events", []),
        "window_from": payload.get("from"),
        "window_to": payload.get("to"),
        "threshold_pp": payload.get("threshold_pp", threshold_pp),
        "selected_league": league or "",
        "selected_hours": hours_ahead,
        "league_options": _league_options(key),
        "window_options": _WINDOW_OPTIONS,
        "active_tab": "picks",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "Picks"},
        ],
    }
    return render(request, "portal/analytics/picks.html", ctx)


@require_paid
def analytics_bets(request):
    """Phase D — placeholder. Bet log + equity curve."""
    ctx = {
        "active_tab": "bets",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "My bets"},
        ],
    }
    return render(request, "portal/analytics/bets.html", ctx)
