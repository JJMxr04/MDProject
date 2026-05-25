"""Thin httpx wrapper around the aggrigator /v1/analytics/* endpoints.

Sync calls (Django views are sync). Every method returns a parsed dict /
list — never raises on transport failure; on error returns an empty
shape and logs the cause. Portal templates render an empty-state when
the result is empty, so a flaky aggrigator never blanks the page.

Base URL comes from ``settings.AGGRIGATOR_BASE_URL`` (defaults to
``http://localhost:8001`` for local dev).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 4.0  # seconds; analytics queries are read-only + indexed


def _base_url() -> str:
    return (getattr(settings, "AGGRIGATOR_BASE_URL", "") or "").rstrip("/")


def _get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    tenant_key: str | None = None,
) -> Any:
    base = _base_url()
    if not base:
        logger.warning(
            "AGGRIGATOR_BASE_URL not configured — analytics call to %s returns empty",
            path,
        )
        return None
    url = f"{base}{path}"
    headers: dict[str, str] = {}
    if tenant_key:
        # Authenticate as the requesting MDProject user. The aggrigator's
        # require_pro_user dep reads this header to look up the
        # TenantApiKey row + verify subscription tier. Without it,
        # every /v1/analytics/* call gets 401.
        headers["X-Aggrigator-Tenant-Key"] = tenant_key

    # Profile passthrough: when the inbound MDProject request set the
    # X-Profile-Aggrigator header and AGGRIGATOR_PROFILE_PASSTHROUGH is
    # on, append ?profile=1 so the aggrigator returns a pyinstrument
    # flame graph instead of JSON. The HTML is captured into the
    # middleware's per-request bucket; we return {} so the view doesn't
    # crash trying to read normal fields. See
    # core/middleware/profile_passthrough.py for the response swap.
    from core.middleware.profile_passthrough import (
        add_capture,
        is_active as _profile_active,
    )
    effective_params: dict[str, Any] = dict(params or {})
    profile_mode = _profile_active()
    if profile_mode:
        effective_params["profile"] = "1"

    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.get(url, params=effective_params, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("aggrigator %s failed: %s", path, exc)
        return None
    if resp.status_code != 200:
        logger.warning(
            "aggrigator %s returned %d: %s", path, resp.status_code, resp.text[:200],
        )
        return None
    if profile_mode:
        add_capture(resp.text)
        return {}
    try:
        return resp.json()
    except ValueError as exc:
        logger.warning("aggrigator %s body not JSON: %s", path, exc)
        return None


def _write(
    method: str,
    path: str,
    json_body: Any | None = None,
    *,
    tenant_key: str | None = None,
) -> dict:
    """POST / PATCH / DELETE helper. Returns the parsed response dict on
    2xx, or ``{"_error": str, "_status": int}`` on failure — bet write
    endpoints lean on this shape so the view layer can show validation
    errors without raising. 204 No Content collapses to ``{"_deleted": True}``."""
    base = _base_url()
    if not base:
        return {"_error": "AGGRIGATOR_BASE_URL not configured", "_status": 0}
    url = f"{base}{path}"
    headers: dict[str, str] = {}
    if tenant_key:
        headers["X-Aggrigator-Tenant-Key"] = tenant_key
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.request(
                method, url, json=json_body, headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("aggrigator %s %s failed: %s", method, path, exc)
        return {"_error": str(exc), "_status": 0}
    if resp.status_code == 204:
        return {"_deleted": True}
    if not (200 <= resp.status_code < 300):
        text = resp.text[:500]
        logger.warning("aggrigator %s %s returned %d: %s", method, path, resp.status_code, text)
        return {"_error": text, "_status": resp.status_code}
    try:
        return resp.json()
    except ValueError as exc:
        return {"_error": f"non-JSON body: {exc}", "_status": resp.status_code}


def _post(path: str, body: Any, *, tenant_key: str | None = None) -> dict:
    return _write("POST", path, body, tenant_key=tenant_key)


def _patch(path: str, body: Any, *, tenant_key: str | None = None) -> dict:
    return _write("PATCH", path, body, tenant_key=tenant_key)


def _delete(path: str, *, tenant_key: str | None = None) -> dict:
    return _write("DELETE", path, None, tenant_key=tenant_key)


def events_today(
    *,
    league: str | None = None,
    hours_ahead: int = 72,
    tenant_key: str | None = None,
) -> dict:
    """Upcoming events with model_prob + has_live_odds + best_edge per row.

    Returns ``{from, to, events: [...]}`` or empty dict on transport
    failure. Per the 2026-05-19 redesign — see
    plans/analytics/dashboard_and_data/06-upcoming-and-picks.md."""
    params: dict[str, Any] = {"hours_ahead": hours_ahead}
    if league:
        params["league"] = league
    body = _get("/v1/analytics/events/today", params, tenant_key=tenant_key)
    if isinstance(body, dict):
        return body
    return {"from": None, "to": None, "events": []}


def picks(
    *,
    threshold_pp: float = 3.0,
    league: str | None = None,
    hours_ahead: int = 72,
    tenant_key: str | None = None,
) -> dict:
    """Threshold-filtered subset of /events/today, sorted by edge DESC."""
    params: dict[str, Any] = {
        "threshold_pp": threshold_pp,
        "hours_ahead": hours_ahead,
    }
    if league:
        params["league"] = league
    body = _get("/v1/analytics/picks", params, tenant_key=tenant_key)
    if isinstance(body, dict):
        return body
    return {"from": None, "to": None, "threshold_pp": threshold_pp, "events": []}


def event_live_odds(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Best price per side + vig-adjusted implied probs for one event.

    Returns ``{event_id, fetched_at, markets, reason}`` or empty dict on
    transport failure. ``markets=[]`` plus a populated ``reason`` is the
    standard no-coverage path."""
    body = _get(
        f"/v1/analytics/events/{event_id}/live-odds",
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def event_probabilities(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Model-derived match probabilities for one event.

    Returns ``{event_id, p_home, p_draw, p_away, model_version,
    computed_at, model_inputs, is_pre_match_snapshot, reason}`` or
    empty dict on transport failure. ``model_version`` is null when the
    sport has no model yet (Phase B is soccer-only)."""
    body = _get(
        f"/v1/analytics/events/{event_id}/probabilities",
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def event_context(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Form-into-match + H2H for the event detail page. Empty dict on failure."""
    body = _get(
        f"/v1/analytics/events/{event_id}/context",
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def event_historical_stats(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Season-context stats for a settled event's two teams. Empty dict on
    transport failure. Past-event-only — future events return
    ``reason="not_finalized"`` with null team blocks."""
    body = _get(
        f"/v1/analytics/events/{event_id}/historical-stats",
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def event_best_prices(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Return ``{event_id, selections: [...]}`` or empty dict on failure."""
    body = _get(
        f"/v1/analytics/events/{event_id}/best-prices",
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def disagreements(
    *,
    threshold_pct: float = 2.0,
    hours_ahead: int = 24,
    limit: int = 25,
    tenant_key: str | None = None,
) -> dict:
    """Return ``{rows: [...], threshold_pct}`` or empty rows on failure."""
    body = _get(
        "/v1/analytics/disagreements",
        {
            "threshold_pct": threshold_pct,
            "hours_ahead": hours_ahead,
            "limit": limit,
        },
        tenant_key=tenant_key,
    )
    if isinstance(body, dict):
        return body
    return {"rows": [], "threshold_pct": threshold_pct}


def list_leagues(*, tenant_key: str | None = None) -> dict:
    """League catalog with summary counts. Empty dict on failure."""
    body = _get("/v1/analytics/leagues", tenant_key=tenant_key)
    return body if isinstance(body, dict) else {}


def league_fixtures(
    league_id: str,
    *,
    season: str | None = None,
    team_id: str | None = None,
    tenant_key: str | None = None,
) -> dict:
    """Fixtures for one league + season. Empty dict on failure."""
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    if team_id:
        params["team_id"] = team_id
    body = _get(
        f"/v1/analytics/leagues/{league_id}/fixtures",
        params or None,
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def league_standings(
    league_id: str,
    *,
    season: str | None = None,
    tenant_key: str | None = None,
) -> dict:
    """Season standings computed from settled events. Empty dict on failure."""
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    body = _get(
        f"/v1/analytics/leagues/{league_id}/standings",
        params or None,
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def team_summary(
    team_id: str,
    *,
    season: str | None = None,
    tenant_key: str | None = None,
) -> dict:
    """Per-team summary — form, season stats, H2H. Empty dict on failure."""
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    body = _get(
        f"/v1/analytics/teams/{team_id}/summary",
        params or None,
        tenant_key=tenant_key,
    )
    return body if isinstance(body, dict) else {}


def list_bets(
    *,
    status_filter: str | None = None,
    tenant_key: str | None = None,
) -> list[dict]:
    """List the caller's bets, newest first. Empty list on transport failure."""
    params: dict[str, Any] = {"limit": 500}
    if status_filter and status_filter != "all":
        params["status"] = status_filter
    body = _get("/v1/analytics/bets", params, tenant_key=tenant_key)
    return body if isinstance(body, list) else []


def bet_summary(*, tenant_key: str | None = None) -> dict:
    """Aggregates + equity curve + ROI-by-bucket. Empty dict on failure."""
    body = _get("/v1/analytics/bets/summary", tenant_key=tenant_key)
    return body if isinstance(body, dict) else {}


def create_bet(payload: dict, *, tenant_key: str | None = None) -> dict:
    """POST /v1/analytics/bets. Returns the created bet dict, or
    ``{"_error": ..., "_status": ...}`` on failure so the view can
    surface a meaningful message."""
    return _post("/v1/analytics/bets", payload, tenant_key=tenant_key)


def update_bet(
    bet_id: str,
    payload: dict,
    *,
    tenant_key: str | None = None,
) -> dict:
    """PATCH /v1/analytics/bets/{id}. Returns the updated bet or error dict."""
    return _patch(f"/v1/analytics/bets/{bet_id}", payload, tenant_key=tenant_key)


def delete_bet(bet_id: str, *, tenant_key: str | None = None) -> dict:
    """DELETE /v1/analytics/bets/{id}. Returns ``{"_deleted": True}`` on
    success, error dict otherwise."""
    return _delete(f"/v1/analytics/bets/{bet_id}", tenant_key=tenant_key)


def event_detail(event_id: str) -> dict:
    """Plain event detail from the legacy ``/v1/events/{id}`` endpoint —
    teams / scores / status. Pairs with probabilities + best-prices for
    the Tonight detail panel.

    No tenant key required — /v1/events/{id} is intentionally public
    (see subscription-plan/05-access-control.md §3)."""
    body = _get(f"/v1/events/{event_id}")
    return body if isinstance(body, dict) else {}
