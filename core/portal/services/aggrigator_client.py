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
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.get(url, params=params or {}, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("aggrigator %s failed: %s", path, exc)
        return None
    if resp.status_code != 200:
        logger.warning(
            "aggrigator %s returned %d: %s", path, resp.status_code, resp.text[:200],
        )
        return None
    try:
        return resp.json()
    except ValueError as exc:
        logger.warning("aggrigator %s body not JSON: %s", path, exc)
        return None


def events_today(
    *,
    sport: str | None = None,
    league: str | None = None,
    hours_ahead: int = 24,
    tenant_key: str | None = None,
) -> list[dict]:
    """Return the Tonight list. Empty list on failure or no events."""
    params: dict[str, Any] = {"hours_ahead": hours_ahead}
    if sport:
        params["sport"] = sport
    if league:
        params["league"] = league
    body = _get("/v1/analytics/events/today", params, tenant_key=tenant_key)
    return body if isinstance(body, list) else []


def event_probabilities(event_id: str, *, tenant_key: str | None = None) -> dict:
    """Return ``{event_id, markets: [...]}`` or empty dict on failure."""
    body = _get(
        f"/v1/analytics/events/{event_id}/probabilities",
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


def event_detail(event_id: str) -> dict:
    """Plain event detail from the legacy ``/v1/events/{id}`` endpoint —
    teams / scores / status. Pairs with probabilities + best-prices for
    the Tonight detail panel.

    No tenant key required — /v1/events/{id} is intentionally public
    (see subscription-plan/05-access-control.md §3)."""
    body = _get(f"/v1/events/{event_id}")
    return body if isinstance(body, dict) else {}
