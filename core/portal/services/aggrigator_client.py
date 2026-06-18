"""Thin httpx wrapper around the aggrigator /v1/analytics/* endpoints.

Sync calls (Django views are sync). Every method returns a parsed dict /
list — never raises on transport failure; on error returns an empty
shape and logs the cause. Portal templates render an empty-state when
the result is empty, so a flaky aggrigator never blanks the page.

Auth (plan §6.4, roadmap Phase 2): every call carries the single
service-tenant key (``settings.AGGRIGATOR_SERVICE_KEY``); the aggregator
authenticates the *service*, not the subscriber — tier gating lives in
MDProject's ``@require_paid``. Per-user data (bets) additionally asserts
the acting user via ``X-Acting-User: <User.public_id>``; only the
service tenant may assert, so the header is inert from any other key.

Base URL comes from ``settings.AGGRIGATOR_BASE_URL`` (defaults to
``http://localhost:8001`` for local dev).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from core.event.providers.aggregator_client import proxy_logo_url

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 4.0  # seconds; analytics queries are read-only + indexed


def _proxy_team_logos(payload: Any) -> Any:
    """Rewrite every nested ``logo_url`` to MDProject's same-origin proxy.

    Analytics payloads (h2h_last_5, form blocks) embed raw aggregator
    ``/v1/teams/{id}/logo`` URLs that reach the browser via the detail
    page's json_script blob and the portal analytics API. Left raw they'd
    hit the key-gated aggregator directly (→401). Walks dicts/lists in
    place and returns ``payload``; idempotent, since ``proxy_logo_url``
    passes through already-proxied and non-logo values.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "logo_url" and (value is None or isinstance(value, str)):
                payload[key] = proxy_logo_url(value)
            else:
                _proxy_team_logos(value)
    elif isinstance(payload, list):
        for item in payload:
            _proxy_team_logos(item)
    return payload


def _base_url() -> str:
    return (getattr(settings, "AGGRIGATOR_BASE_URL", "") or "").rstrip("/")


def _headers(acting_user_id: Any | None = None) -> dict[str, str]:
    """Service key always; acting-user assertion only for per-user data."""
    headers: dict[str, str] = {}
    service_key = (getattr(settings, "AGGRIGATOR_SERVICE_KEY", "") or "").strip()
    if service_key:
        headers["X-Aggrigator-Tenant-Key"] = service_key
    else:
        # Keyless reads still pass while the aggregator's
        # AGG_REQUIRE_KEY_FOR_READS flag is false — but every one logs a
        # WARNING over there, and bets calls 401. Configure the key.
        logger.warning("AGGRIGATOR_SERVICE_KEY not configured — calling keyless")
    if acting_user_id:
        headers["X-Acting-User"] = str(acting_user_id)
    return headers


def _get(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    acting_user_id: Any | None = None,
) -> Any:
    base = _base_url()
    if not base:
        logger.warning(
            "AGGRIGATOR_BASE_URL not configured — analytics call to %s returns empty",
            path,
        )
        return None
    url = f"{base}{path}"
    headers = _headers(acting_user_id)

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
    acting_user_id: Any | None = None,
) -> dict:
    """POST / PATCH / DELETE helper. Returns the parsed response dict on
    2xx, or ``{"_error": str, "_status": int}`` on failure — bet write
    endpoints lean on this shape so the view layer can show validation
    errors without raising. 204 No Content collapses to ``{"_deleted": True}``."""
    base = _base_url()
    if not base:
        return {"_error": "AGGRIGATOR_BASE_URL not configured", "_status": 0}
    url = f"{base}{path}"
    headers = _headers(acting_user_id)
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


def _post(path: str, body: Any, *, acting_user_id: Any | None = None) -> dict:
    return _write("POST", path, body, acting_user_id=acting_user_id)


def _patch(path: str, body: Any, *, acting_user_id: Any | None = None) -> dict:
    return _write("PATCH", path, body, acting_user_id=acting_user_id)


def _delete(path: str, *, acting_user_id: Any | None = None) -> dict:
    return _write("DELETE", path, None, acting_user_id=acting_user_id)


def events_today(
    *,
    league: str | None = None,
    hours_ahead: int = 72,
) -> dict:
    """Upcoming events with model_prob + has_live_odds + best_edge per row.

    Returns ``{from, to, events: [...]}`` or empty dict on transport
    failure. Per the 2026-05-19 redesign — see
    plans/analytics/dashboard_and_data/06-upcoming-and-picks.md."""
    params: dict[str, Any] = {"hours_ahead": hours_ahead}
    if league:
        params["league"] = league
    body = _get("/v1/analytics/events/today", params)
    if isinstance(body, dict):
        return body
    return {"from": None, "to": None, "events": []}


def picks(
    *,
    threshold_pp: float = 3.0,
    league: str | None = None,
    hours_ahead: int = 72,
) -> dict:
    """Threshold-filtered subset of /events/today, sorted by edge DESC."""
    params: dict[str, Any] = {
        "threshold_pp": threshold_pp,
        "hours_ahead": hours_ahead,
    }
    if league:
        params["league"] = league
    body = _get("/v1/analytics/picks", params)
    if isinstance(body, dict):
        return body
    return {"from": None, "to": None, "threshold_pp": threshold_pp, "events": []}


def event_live_odds(event_id: str) -> dict:
    """Best price per side + vig-adjusted implied probs for one event.

    Returns ``{event_id, fetched_at, markets, reason}`` or empty dict on
    transport failure. ``markets=[]`` plus a populated ``reason`` is the
    standard no-coverage path."""
    body = _get(
        f"/v1/analytics/events/{event_id}/live-odds",
    )
    return body if isinstance(body, dict) else {}


def event_probabilities(event_id: str) -> dict:
    """Model-derived match probabilities for one event.

    Returns ``{event_id, p_home, p_draw, p_away, model_version,
    computed_at, model_inputs, is_pre_match_snapshot, reason}`` or
    empty dict on transport failure. ``model_version`` is null when the
    sport has no model yet (Phase B is soccer-only)."""
    body = _get(
        f"/v1/analytics/events/{event_id}/probabilities",
    )
    return body if isinstance(body, dict) else {}


def event_context(event_id: str) -> dict:
    """Form-into-match + H2H for the event detail page. Empty dict on failure."""
    body = _get(
        f"/v1/analytics/events/{event_id}/context",
    )
    return _proxy_team_logos(body) if isinstance(body, dict) else {}


def event_historical_stats(event_id: str) -> dict:
    """Season-context stats for a settled event's two teams. Empty dict on
    transport failure. Past-event-only — future events return
    ``reason="not_finalized"`` with null team blocks."""
    body = _get(
        f"/v1/analytics/events/{event_id}/historical-stats",
    )
    return _proxy_team_logos(body) if isinstance(body, dict) else {}


def event_best_prices(event_id: str) -> dict:
    """Return ``{event_id, selections: [...]}`` or empty dict on failure."""
    body = _get(
        f"/v1/analytics/events/{event_id}/best-prices",
    )
    return body if isinstance(body, dict) else {}


def disagreements(
    *,
    threshold_pct: float = 2.0,
    hours_ahead: int = 24,
    limit: int = 25,
) -> dict:
    """Return ``{rows: [...], threshold_pct}`` or empty rows on failure."""
    body = _get(
        "/v1/analytics/disagreements",
        {
            "threshold_pct": threshold_pct,
            "hours_ahead": hours_ahead,
            "limit": limit,
        },
    )
    if isinstance(body, dict):
        return body
    return {"rows": [], "threshold_pct": threshold_pct}


def list_leagues() -> dict:
    """League catalog with summary counts. Empty dict on failure."""
    body = _get("/v1/analytics/leagues")
    return body if isinstance(body, dict) else {}


def league_fixtures(
    league_id: str,
    *,
    season: str | None = None,
    team_id: str | None = None,
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
    )
    return body if isinstance(body, dict) else {}


def league_standings(
    league_id: str,
    *,
    season: str | None = None,
) -> dict:
    """Season standings computed from settled events. Empty dict on failure."""
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    body = _get(
        f"/v1/analytics/leagues/{league_id}/standings",
        params or None,
    )
    return body if isinstance(body, dict) else {}


def team_summary(
    team_id: str,
    *,
    season: str | None = None,
) -> dict:
    """Per-team summary — form, season stats, H2H. Empty dict on failure."""
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    body = _get(
        f"/v1/analytics/teams/{team_id}/summary",
        params or None,
    )
    return body if isinstance(body, dict) else {}


# ---- bets: per-user data — every call asserts the acting user --------------
#
# ``acting_user_id`` is the MDProject ``User.public_id`` (the aggregator's
# ``external_user_id``). The aggregator attributes the bet rows to that
# tenant user — never to the service tenant.


def list_bets(
    *,
    acting_user_id: Any,
    status_filter: str | None = None,
) -> list[dict]:
    """List the acting user's bets, newest first. Empty list on transport failure."""
    params: dict[str, Any] = {"limit": 500}
    if status_filter and status_filter != "all":
        params["status"] = status_filter
    body = _get("/v1/analytics/bets", params, acting_user_id=acting_user_id)
    return body if isinstance(body, list) else []


def bet_summary(*, acting_user_id: Any) -> dict:
    """Aggregates + equity curve + ROI-by-bucket. Empty dict on failure."""
    body = _get("/v1/analytics/bets/summary", acting_user_id=acting_user_id)
    return body if isinstance(body, dict) else {}


def create_bet(payload: dict, *, acting_user_id: Any) -> dict:
    """POST /v1/analytics/bets. Returns the created bet dict, or
    ``{"_error": ..., "_status": ...}`` on failure so the view can
    surface a meaningful message."""
    return _post("/v1/analytics/bets", payload, acting_user_id=acting_user_id)


def update_bet(
    bet_id: str,
    payload: dict,
    *,
    acting_user_id: Any,
) -> dict:
    """PATCH /v1/analytics/bets/{id}. Returns the updated bet or error dict."""
    return _patch(
        f"/v1/analytics/bets/{bet_id}", payload, acting_user_id=acting_user_id,
    )


def delete_bet(bet_id: str, *, acting_user_id: Any) -> dict:
    """DELETE /v1/analytics/bets/{id}. Returns ``{"_deleted": True}`` on
    success, error dict otherwise."""
    return _delete(f"/v1/analytics/bets/{bet_id}", acting_user_id=acting_user_id)


def event_detail(event_id: str) -> dict:
    """Plain event detail from the legacy ``/v1/events/{id}`` endpoint —
    teams / scores / status. Pairs with probabilities + best-prices for
    the Tonight detail panel.

    No tenant key required — /v1/events/{id} is intentionally public
    (see subscription-plan/05-access-control.md §3)."""
    body = _get(f"/v1/events/{event_id}")
    return body if isinstance(body, dict) else {}
