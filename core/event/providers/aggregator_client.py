"""Outbound HTTP client used by MDProject to read from the aggregator.

The Django portal previously read events/bookmakers/markets/odds out of its
local DB. After the cutover (plan §7.4), it calls the aggregator instead for
*new-event discovery* — already-selected events stay local. This module
implements the same surface as the legacy ``SportsGameOddsClient`` so the
``providers/__init__.py`` factory can swap to it in a single line.

The aggregator's read endpoints are public — set ``AGGRIGATOR_BASE_URL`` in
MDProject settings and that's all the client needs. HMAC-signed webhook
delivery uses ``AGGRIGATOR_WEBHOOK_SECRET`` separately on the receive path.

Conditional GETs (ETag / If-None-Match) — see ``_get`` for the flow. The
aggregator emits ``Cache-Control`` + ``ETag`` on read endpoints; we cache
the (etag, body) pair in Django's cache and replay the etag on the next
request. A 304 returns the cached body without re-parsing JSON.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Iterator
from urllib.parse import urlencode

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


# Default cache TTL when the upstream response omits Cache-Control or we
# can't parse a max-age. Long enough to amortize the round-trip, short
# enough that staleness windows never exceed the existing per-endpoint
# 30-600s settings on the aggregator side.
_DEFAULT_CACHE_TTL = 60

# Cap stored cache TTL even when the server says "max-age=86400" or
# similar — defensive against misconfiguration on the aggregator side.
_MAX_CACHE_TTL = 60 * 60

_CACHE_VERSION = "v1"
_MAX_AGE_RE = re.compile(r"max-age\s*=\s*(\d+)", re.IGNORECASE)


def _parse_max_age(cache_control_header: str | None) -> int | None:
    if not cache_control_header:
        return None
    match = _MAX_AGE_RE.search(cache_control_header)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def absolutize_logo_url(url: str | None) -> str | None:
    """Resolve a possibly-relative aggregator logo URL to an absolute,
    browser-reachable one.

    The aggregator emits a *relative* ``/v1/teams/{id}/logo`` when its own
    ``AGG_PUBLIC_BASE_URL`` is unset; a browser would resolve that against
    MDProject's origin (→ 404). Prefix it with the aggregator's public
    origin: prefer ``AGG_PUBLIC_BASE`` (browser-facing), else fall back to
    the server-to-server ``AGGRIGATOR_BASE_URL`` (correct for local dev and
    single-origin deploys). Absolute URLs and non-URLs pass through
    unchanged, so this is idempotent.
    """
    if not url or not url.startswith("/"):
        return url
    from django.conf import settings

    base = (
        (getattr(settings, "AGG_PUBLIC_BASE", "") or "")
        or getattr(settings, "AGGRIGATOR_BASE_URL", "")
    ).rstrip("/")
    return f"{base}{url}" if base else url


def _cache_key(method: str, url: str, params: dict) -> str:
    # Stable, length-bounded key — Django's Redis backend doesn't like
    # giant keys, and Memcached caps at 250 bytes. Hash the URL+params
    # so the key is constant-length regardless of payload.
    canonical = f"{method} {url}?{urlencode(sorted(params.items()))}"
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"aggrigator:{_CACHE_VERSION}:cond:{digest}"


class AggrigatorError(Exception):
    """Any non-recoverable aggregator-side failure."""


class AggrigatorRateLimited(AggrigatorError):
    """The aggregator's rate limiter returned 429. Carries the server's
    ``Retry-After`` (seconds) so callers back off instead of hammering the
    tripped limiter — distinct from a real failure or a 404 miss."""

    def __init__(self, team_id: str, retry_after: int):
        self.retry_after = retry_after
        super().__init__(
            f"GET logo {team_id} rate limited (429); retry after {retry_after}s"
        )


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

    def get_team_logo_bytes(self, team_id: str):
        """Fetch a team crest from the aggregator's keyless endpoint.

        Returns ``(bytes, content_type, etag)`` on 200, ``None`` on 404.
        Binary endpoint — bypasses the JSON ``_get`` path.
        """
        url = f"{self.base_url}/v1/teams/{team_id}/logo"
        try:
            resp = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AggrigatorError(f"GET logo {team_id} failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code == 429:
            raw = resp.headers.get("Retry-After")
            try:
                retry_after = int(raw) if raw else 60
            except (TypeError, ValueError):
                retry_after = 60
            raise AggrigatorRateLimited(team_id, retry_after)
        if resp.status_code >= 400:
            raise AggrigatorError(
                f"GET logo {team_id} returned {resp.status_code}"
            )
        return (
            resp.content,
            resp.headers.get("Content-Type", "image/png"),
            resp.headers.get("ETag"),
        )

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
        """GET with ETag conditional-request handling.

        Flow:
          1. Build a stable cache key from URL+params.
          2. Look up any cached (etag, body) pair from a prior 200.
          3. If present, send ``If-None-Match: <etag>``.
          4. If the server responds 304, return the cached body —
             no JSON parse, no payload transfer.
          5. On 200, parse JSON, cache (etag, body) with TTL from
             ``Cache-Control: max-age=N`` (fallback: _DEFAULT_CACHE_TTL).

        The cache lookup is best-effort: a Redis blip just bypasses
        the optimization without erroring the request.
        """
        url = f"{self.base_url}{path}"
        clean = {k: v for k, v in (params or {}).items() if v is not None}

        cache_key = _cache_key("GET", url, clean)
        cached = _safe_cache_get(cache_key)
        headers: dict[str, str] = {}
        if cached and isinstance(cached, dict) and "etag" in cached:
            headers["If-None-Match"] = cached["etag"]

        try:
            resp = self.session.get(
                url, params=clean, headers=headers, timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise AggrigatorError(f"GET {path} failed: {exc}") from exc

        if resp.status_code == 304:
            if cached and "body" in cached:
                return cached["body"]
            # Server said "not modified" but we have no cached body to
            # serve — refetch unconditionally as a safety valve.
            logger.info(
                "aggrigator 304 without cached body — refetching %s", path,
            )
            return self._get_unconditional(url, clean)

        if resp.status_code == 404:
            _safe_cache_delete(cache_key)
            return None
        if resp.status_code >= 400:
            raise AggrigatorError(
                f"GET {path} returned {resp.status_code}: {resp.text[:200]}"
            )

        body = resp.json()
        etag = resp.headers.get("ETag")
        if etag:
            ttl = _parse_max_age(resp.headers.get("Cache-Control"))
            if ttl is None:
                ttl = _DEFAULT_CACHE_TTL
            ttl = max(1, min(ttl, _MAX_CACHE_TTL))
            _safe_cache_set(cache_key, {"etag": etag, "body": body}, ttl)
        return body

    def _get_unconditional(self, url: str, params: dict):
        """Safety-valve path: refetch when server returned 304 but we
        lost the cached body (eviction, restart, etc.)."""
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise AggrigatorError(f"GET {url} (refetch) failed: {exc}") from exc
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise AggrigatorError(
                f"GET {url} (refetch) returned {resp.status_code}: {resp.text[:200]}"
            )
        return resp.json()


def _safe_cache_get(key):
    try:
        return cache.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("aggrigator cache.get(%s) failed: %s", key, exc)
        return None


def _safe_cache_set(key, value, ttl):
    try:
        cache.set(key, value, timeout=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.debug("aggrigator cache.set(%s) failed: %s", key, exc)


def _safe_cache_delete(key):
    try:
        cache.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("aggrigator cache.delete(%s) failed: %s", key, exc)
