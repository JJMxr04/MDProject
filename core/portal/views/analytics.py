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
    """Phase B — placeholder. Past = score; future = model + live odds."""
    event = aggrigator_client.event_detail(event_id)
    ctx = {
        "event_id": event_id,
        "event": event,
        "active_tab": "explore",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": f"Event {event_id}"},
        ],
    }
    return render(request, "portal/analytics/event.html", ctx)


@require_paid
def analytics_upcoming(request):
    """Phase C — placeholder. Next-24h fixtures with model prob + live odds."""
    ctx = {
        "active_tab": "upcoming",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "Upcoming"},
        ],
    }
    return render(request, "portal/analytics/upcoming.html", ctx)


@require_paid
def analytics_picks(request):
    """Phase C — placeholder. +EV pick filter on top of /upcoming/."""
    try:
        threshold_pp = float(request.GET.get("threshold_pp") or 3.0)
    except ValueError:
        threshold_pp = 3.0
    ctx = {
        "threshold_pp": threshold_pp,
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
