"""Portal analytics views — score-driven explore + decision dashboard.

Default landing is the league browser (Explore), per
``plans/analytics/dashboard_and_data/01-information-architecture.md``.
The previous Tonight / Edge dashboard assumed months of stored
bookmaker odds; that data source is gone (see plan 00-overview.md).

Pages in this module:
- ``analytics_landing``      → league card grid (default landing)
- ``analytics_league``       → fixtures + standings for one league
- ``analytics_team``         → team form, H2H, season stats
- ``analytics_picks``        → +EV pick filter (Phase C placeholder)
- ``analytics_bets``         → bet log (Phase D placeholder)

Single-event detail and the upcoming list moved out of /analytics/ on
2026-05-21 — they now live on the events surface and render analytics
inline (gated by entitlement). The 301 shims for the old URLs are
defined at the top of this module.

Views degrade gracefully when the aggrigator is unreachable — the
client returns empty shapes and the templates render empty-state cards.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from core.billing.decorators import require_paid
from core.portal.services import aggrigator_client

# ---- Permanent redirects --------------------------------------------------
# Event detail + upcoming list moved out of /analytics/ on 2026-05-21 —
# the events page is now the canonical surface and analytics renders
# inline there, gated by entitlement. These shims keep old links alive.


@login_required(login_url="/auth/login/")
def analytics_event_redirect(request, event_id: str):
    return redirect(
        reverse("core-portal:upcoming-events-detail", args=[event_id]),
        permanent=True,
    )


@login_required(login_url="/auth/login/")
def analytics_upcoming_redirect(request):
    return redirect(
        reverse("core-portal:upcoming-events"),
        permanent=True,
    )


def _acting(request):
    """The aggregator-side identity for per-user data calls: User.public_id
    (= tenant_user.external_user_id). Shared-data calls don't need it —
    the service key in the client covers auth (plan §6.4)."""
    return request.user.public_id


@require_paid
def analytics_landing(request):
    payload = aggrigator_client.list_leagues()
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

    fixtures = aggrigator_client.league_fixtures(league_id, season=season)
    standings = aggrigator_client.league_standings(league_id, season=season)

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
    payload = aggrigator_client.team_summary(team_id, season=season)
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


def _league_options() -> list[dict]:
    """Pull the league catalog for the filter dropdown. Empty list if
    the aggrigator is unreachable."""
    payload = aggrigator_client.list_leagues()
    return payload.get("leagues") or []


@require_paid
def analytics_picks(request):
    """+EV picks — same data as Upcoming, filtered by best_edge ≥ threshold."""
    league = request.GET.get("league") or None
    hours_ahead = _parse_window(request.GET.get("hours_ahead"))
    try:
        # nosemgrep: python.django.security.nan-injection.nan-injection -- NaN/inf rejected by the guard below
        threshold_pp = float(request.GET.get("threshold_pp") or 3.0)
    except (TypeError, ValueError):
        threshold_pp = 3.0
    else:
        # Reject NaN/inf (NaN-injection): NaN compares false to everything and
        # would silently break the downstream edge filter.
        if threshold_pp != threshold_pp or threshold_pp in (float("inf"), float("-inf")):
            threshold_pp = 3.0
    payload = aggrigator_client.picks(
        threshold_pp=threshold_pp, league=league, hours_ahead=hours_ahead,
    )
    ctx = {
        "events": payload.get("events", []),
        "window_from": payload.get("from"),
        "window_to": payload.get("to"),
        "threshold_pp": payload.get("threshold_pp", threshold_pp),
        "selected_league": league or "",
        "selected_hours": hours_ahead,
        "league_options": _league_options(),
        "window_options": _WINDOW_OPTIONS,
        "active_tab": "picks",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "Picks"},
        ],
    }
    return render(request, "portal/analytics/picks.html", ctx)


_BET_SELECTION_TYPES = (
    ("moneyline_home", "Moneyline — Home"),
    ("moneyline_away", "Moneyline — Away"),
    ("moneyline_draw", "Moneyline — Draw"),
    ("total_over", "Total — Over"),
    ("total_under", "Total — Under"),
    ("spread_home", "Spread — Home"),
    ("spread_away", "Spread — Away"),
    ("other", "Other / prop / parlay"),
)

_BET_STATUS_FILTERS = (
    ("all", "All"),
    ("open", "Open"),
    ("settled", "Settled"),
)


def _coerce_decimal(raw: str) -> str | None:
    """Strip and validate a free-form decimal input. Returns the trimmed
    string when it parses as a positive Decimal, None otherwise."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        from decimal import Decimal as _D
        v = _D(raw)
    except Exception:
        return None
    if v <= 0:
        return None
    return str(v)


@require_paid
def analytics_bets(request):
    """Bet log + summary + equity curve. POST creates a new bet."""
    acting = _acting(request)
    form_errors: list[str] = []
    form_values: dict = {}

    if request.method == "POST":
        form_values = {k: request.POST.get(k, "") for k in (
            "label", "selection_type", "bookmaker", "stake",
            "decimal_odds", "event_id", "placed_at", "note",
        )}
        stake = _coerce_decimal(form_values["stake"])
        odds = _coerce_decimal(form_values["decimal_odds"])
        if not form_values["label"].strip():
            form_errors.append("Label is required.")
        if form_values["selection_type"] not in dict(_BET_SELECTION_TYPES):
            form_errors.append("Pick a selection type.")
        if stake is None:
            form_errors.append("Stake must be a positive decimal.")
        if odds is None:
            form_errors.append("Decimal odds must be a positive decimal.")
        if odds is not None and float(odds) < 1.01:
            form_errors.append("Decimal odds must be ≥ 1.01.")

        if not form_errors:
            payload = {
                "label": form_values["label"].strip(),
                "selection_type": form_values["selection_type"],
                "stake": stake,
                "decimal_odds": odds,
            }
            if form_values["bookmaker"].strip():
                payload["bookmaker"] = form_values["bookmaker"].strip()
            if form_values["event_id"].strip():
                payload["event_id"] = form_values["event_id"].strip()
            if form_values["placed_at"].strip():
                payload["placed_at"] = form_values["placed_at"].strip()
            if form_values["note"].strip():
                payload["note"] = form_values["note"].strip()
            resp = aggrigator_client.create_bet(payload, acting_user_id=acting)
            if resp.get("_error"):
                form_errors.append(f"Could not save bet: {resp['_error']}")
            else:
                # Redirect post-redirect-get so refresh doesn't resubmit.
                from django.http import HttpResponseRedirect
                # nosemgrep: python.django.security.injection.open-redirect.open-redirect -- request.path is the server-set URL path (no scheme/host); safe self-redirect
                return HttpResponseRedirect(request.path)

    status_filter = request.GET.get("status") or "all"
    bets = aggrigator_client.list_bets(status_filter=status_filter, acting_user_id=acting)
    summary = aggrigator_client.bet_summary(acting_user_id=acting)

    # Decorate rows with profit_loss for table rendering — Django templates
    # can't do arithmetic on Decimal/float and the API doesn't carry the
    # field (it'd just be derivable junk in the payload).
    for b in bets:
        if b.get("payout") is None or b.get("stake") is None:
            b["profit_loss"] = None
        else:
            try:
                b["profit_loss"] = float(b["payout"]) - float(b["stake"])
            except (TypeError, ValueError):
                b["profit_loss"] = None

    ctx = {
        "bets": bets,
        "bucket_labels": (
            ("By selection type", "selection_type"),
            ("By bookmaker", "bookmaker"),
            ("By odds band", "odds_band"),
        ),
        "summary": summary.get("totals", {}),
        "equity_curve": summary.get("equity_curve", []),
        "roi_by_bucket": summary.get("roi_by_bucket", {}),
        "status_filter": status_filter,
        "selection_types": _BET_SELECTION_TYPES,
        "status_filters": _BET_STATUS_FILTERS,
        "form_errors": form_errors,
        "form_values": form_values,
        "active_tab": "bets",
        "crumbs": [
            {"label": "Analytics", "href": "/web/portal/analytics/"},
            {"label": "My bets"},
        ],
    }
    return render(request, "portal/analytics/bets.html", ctx)


@require_paid
def analytics_bets_action(request, bet_id: str):
    """Inline settle / delete / note edit. Always POST; redirects back to
    the bet list. ``_action`` form field picks the path."""
    from django.http import HttpResponseRedirect
    if request.method != "POST":
        return HttpResponseRedirect("/web/portal/analytics/bets/")
    action = request.POST.get("_action", "")
    acting = _acting(request)
    if action == "delete":
        aggrigator_client.delete_bet(bet_id, acting_user_id=acting)
    elif action == "settle":
        new_status = request.POST.get("settlement_status") or ""
        if new_status:
            aggrigator_client.update_bet(
                bet_id, {"settlement_status": new_status}, acting_user_id=acting,
            )
    elif action == "note":
        aggrigator_client.update_bet(
            bet_id, {"note": request.POST.get("note") or ""}, acting_user_id=acting,
        )
    return HttpResponseRedirect("/web/portal/analytics/bets/")
