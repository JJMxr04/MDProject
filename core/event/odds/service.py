"""On-demand odds fetcher.

Gate every call to SofaScore `/matches/get-all-odds` through this module so that
the monthly quota is respected. Rules in short (see odds-system-plan.md §6.2):

- Response JSON is cached in Redis. A client hit reads the cache first.
- If the cache is older than the freshness threshold *and* the per-event
  monthly counter is below the floor, we fetch, ingest, and re-cache.
- Otherwise we serve the stale payload with `stale=True` in the metadata.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.core.cache import cache
from django.utils import timezone as dj_tz

from core.event.models import Event
from core.event.odds.normalize import ingest_odds
from core.event.sofascore import QuotaExceeded, SofaScoreClient

logger = logging.getLogger(__name__)


PER_EVENT_MONTHLY_CAP = 10

PRE_MATCH_FAR_TTL = timedelta(hours=6)
PRE_MATCH_NEAR_TTL = timedelta(minutes=30)
LIVE_TTL = timedelta(seconds=30)
NEAR_WINDOW = timedelta(hours=24)

RAW_CACHE_TTL = int(timedelta(hours=12).total_seconds())  # backstop


def _raw_cache_key(event_id: int) -> str:
    return f"sofascore:odds:{event_id}"


def _counter_key(event_id: int) -> str:
    return f"sofascore:odds:{event_id}:{datetime.utcnow():%Y-%m}"


def _freshness(event: Event) -> timedelta:
    if event.status_type == "inprogress":
        return LIVE_TTL
    start = event.start_time
    if start is None:
        return PRE_MATCH_FAR_TTL
    if start - dj_tz.now() <= NEAR_WINDOW:
        return PRE_MATCH_NEAR_TTL
    return PRE_MATCH_FAR_TTL


@dataclass
class OddsFetchResult:
    payload: Optional[dict]
    stale: bool
    markets_ingested: int
    calls_this_month: int


def get_event_odds(event: Event, *, force: bool = False) -> OddsFetchResult:
    """Return odds for an event, fetching from SofaScore only if warranted.

    `force=True` bypasses the freshness check but still respects the
    per-event monthly counter.
    """
    raw_key = _raw_cache_key(event.id)
    cached = cache.get(raw_key)
    cached_at: Optional[datetime] = None
    if isinstance(cached, dict):
        ts = cached.get("__cached_at")
        if ts:
            cached_at = datetime.fromisoformat(ts)

    ttl = _freshness(event)
    cache_fresh = (
        cached_at is not None
        and (datetime.now(tz=timezone.utc) - cached_at) < ttl
    )

    if cached and cache_fresh and not force:
        return OddsFetchResult(
            payload=cached.get("payload"),
            stale=False,
            markets_ingested=0,
            calls_this_month=cache.get(_counter_key(event.id), 0),
        )

    counter_key = _counter_key(event.id)
    used = cache.get(counter_key, 0)
    if used >= PER_EVENT_MONTHLY_CAP:
        logger.info(
            "Per-event odds cap reached for event=%s (%s/%s); serving stale",
            event.id,
            used,
            PER_EVENT_MONTHLY_CAP,
        )
        return OddsFetchResult(
            payload=(cached or {}).get("payload") if isinstance(cached, dict) else None,
            stale=True,
            markets_ingested=0,
            calls_this_month=used,
        )

    client = SofaScoreClient()
    try:
        payload = client.get_match_odds(event.id)
    except QuotaExceeded as exc:
        logger.error("Global quota exceeded fetching odds for event=%s: %s", event.id, exc)
        return OddsFetchResult(
            payload=(cached or {}).get("payload") if isinstance(cached, dict) else None,
            stale=True,
            markets_ingested=0,
            calls_this_month=used,
        )

    if payload is None:
        # Network / auth failure — serve stale if we have it
        return OddsFetchResult(
            payload=(cached or {}).get("payload") if isinstance(cached, dict) else None,
            stale=True,
            markets_ingested=0,
            calls_this_month=used,
        )

    cache.set(
        counter_key, used + 1, timeout=60 * 60 * 24 * 40
    )  # 40-day TTL, same as global counter

    markets_ingested = ingest_odds(event, payload)

    cache.set(
        raw_key,
        {"__cached_at": datetime.now(tz=timezone.utc).isoformat(), "payload": payload},
        timeout=RAW_CACHE_TTL,
    )

    return OddsFetchResult(
        payload=payload,
        stale=False,
        markets_ingested=markets_ingested,
        calls_this_month=used + 1,
    )
