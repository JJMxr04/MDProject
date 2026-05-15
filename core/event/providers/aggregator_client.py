"""Outbound HTTP client used by MDProject to read from the aggregator.

The Django portal previously read events/bookmakers/markets/odds out of its
local DB. After the cutover (plan §7.4), it calls the aggregator instead for
*new-event discovery* — already-selected events stay local. This module
implements the same surface as the legacy ``SportsGameOddsClient`` so the
``providers/__init__.py`` factory can swap to it in a single line.

The aggregator's read endpoints are public — set ``AGGRIGATOR_BASE_URL`` in
MDProject settings and that's all the client needs. HMAC-signed webhook
delivery uses ``AGGRIGATOR_WEBHOOK_SECRET`` separately on the receive path.
"""

from __future__ import annotations

import logging
import os
from typing import Iterator

import requests

logger = logging.getLogger(__name__)


class AggrigatorError(Exception):
    """Any non-recoverable aggregator-side failure."""


class AggrigatorClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.environ.get("AGGRIGATOR_BASE_URL", "http://localhost:8001")
        ).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ---- public surface (matches the legacy SportsGameOdds client) --------

    def get_account_usage(self) -> dict:
        # The aggregator owns SGO quota tracking; expose nothing here.
        return {}

    def get_sports(self) -> list[dict]:
        return self._get("/v1/sports") or []

    def get_leagues(self, sport_id: str | None = None) -> list[dict]:
        return self._get("/v1/leagues", params={"sport_id": sport_id}) or []

    def get_bookmakers(self) -> list[dict]:
        return self._get("/v1/bookmakers") or []

    def get_market_types(self, sport_id: str | None = None) -> list[str]:
        """Distinct ``Market.type`` strings the aggregator currently has on
        record. Used by the portal's "What's available" page to render
        the live list of market names instead of a hand-maintained one.
        Returns ``[]`` on an unexpected payload shape — the caller
        tolerates an empty list."""
        body = self._get("/v1/market-types", params={"sport_id": sport_id})
        if not isinstance(body, list):
            return []
        return [t for t in body if isinstance(t, str) and t]

    def list_events(self, **params) -> dict:
        return self._get("/v1/events", params=params) or {}

    def get_event(self, event_id: str, *, include_markets: bool = True) -> dict | None:
        params = {"include": "markets"} if include_markets else None
        body = self._get(f"/v1/events/{event_id}", params=params)
        if not body:
            return None
        return body

    def get_event_markets(self, event_id: str, **params) -> dict:
        return self._get(f"/v1/events/{event_id}/markets", params=params) or {}

    def get_selection_movement(self, selection_id: str, since: str | None = None) -> dict:
        params = {"since": since} if since else None
        return self._get(f"/v1/selections/{selection_id}/movement", params=params) or {}

    def get_events(self, **kwargs) -> Iterator[dict]:
        """Compatibility shim: pages through ``/v1/events`` and yields each
        event dict — same shape as the legacy client returned."""
        page = 1
        while True:
            params = {**kwargs, "page": page, "page_size": 100}
            body = self.list_events(**params)
            for item in body.get("items") or []:
                yield item
            total_pages = body.get("pages") or 1
            if page >= total_pages:
                return
            page += 1

    # ---- transport --------------------------------------------------------

    def _get(self, path: str, params: dict | None = None):
        url = f"{self.base_url}{path}"
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = self.session.get(url, params=clean, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AggrigatorError(f"GET {path} failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise AggrigatorError(
                f"GET {path} returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()
