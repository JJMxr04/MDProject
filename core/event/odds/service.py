"""On-demand event-detail refresh.

Replaces the SofaScore-era per-event ``get-all-odds`` fetcher. SGO returns the
event + odds in one call (``GET /v2/events?eventID=…``), so a single fetch
also refreshes the event's status and embedded teams.

Flow:
- Caller asks for fresh odds on event X (typically because a user opened the
  detail page).
- We consult the per-event freshness tier and the per-event monthly counter.
- If we can fetch, we go to SGO once, normalize, persist, and return.
- If we can't (cap hit / quota exhausted), we serve stale DB rows.

The cron-driven event-list ingest (``EventCron.ingest_league``) handles the
bulk path; this module is for "user is looking at it right now" traffic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as dj_tz

from core.event.crons.eventUpdate import EventCron
from core.event.models import Event, League
from core.event.odds.sgo_normalize import event_spec_from_payload
from core.event.providers import (
    QuotaExceeded,
    SportsGameOddsError,
    get_events_client,
)

logger = logging.getLogger(__name__)


PER_EVENT_MONTHLY_CAP = 8

PRE_MATCH_FAR_TTL = timedelta(hours=6)
PRE_MATCH_NEAR_TTL = timedelta(minutes=30)
LIVE_TTL = timedelta(seconds=60)
NEAR_WINDOW = timedelta(hours=24)


def _last_refresh_key(event_id: str) -> str:
    return f"sgo:event_refresh:{event_id}"


def _counter_key(event_id: str) -> str:
    return f"sgo:event_calls:{event_id}:{datetime.utcnow():%Y-%m}"


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
    event: Optional[Event]
    stale: bool
    markets_ingested: int
    calls_this_month: int


def get_event_odds(event: Event, *, force: bool = False) -> OddsFetchResult:
    """Refresh one event from SGO.

    ``force=True`` bypasses the freshness check but still respects the
    per-event monthly counter. ``settings.EVENTS_DEBUG_FORCE_FRESH=True``
    bypasses both — for local dev against the simulator.
    """
    debug_force = getattr(settings, "EVENTS_DEBUG_FORCE_FRESH", False)

    counter_key = _counter_key(event.id)
    used = cache.get(counter_key, 0)

    last_refresh_at = cache.get(_last_refresh_key(event.id))
    if isinstance(last_refresh_at, str):
        try:
            last_refresh_at = datetime.fromisoformat(last_refresh_at)
        except ValueError:
            last_refresh_at = None

    ttl = _freshness(event)
    if not force and not debug_force and last_refresh_at:
        if (datetime.now(tz=timezone.utc) - last_refresh_at) < ttl:
            return OddsFetchResult(event=event, stale=False, markets_ingested=0, calls_this_month=used)

    if used >= PER_EVENT_MONTHLY_CAP and not debug_force:
        logger.info(
            "Per-event SGO refresh cap reached for event=%s (%s/%s); serving stale",
            event.id, used, PER_EVENT_MONTHLY_CAP,
        )
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)

    client = get_events_client()
    try:
        payload = client.get_event(event.id, include_open_close=True)
    except QuotaExceeded as exc:
        logger.error("Global quota exceeded for event=%s: %s", event.id, exc)
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)
    except SportsGameOddsError as exc:
        logger.warning("SGO error for event=%s: %s", event.id, exc)
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)

    if payload is None:
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)

    spec = event_spec_from_payload(payload)
    if spec is None:
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)

    league = League.objects.filter(id=spec.league_id).first()
    if league is None:
        return OddsFetchResult(event=event, stale=True, markets_ingested=0, calls_this_month=used)

    cron = EventCron(client=client)
    cron._persist(spec, payload, league)

    cache.set(counter_key, used + 1, timeout=60 * 60 * 24 * 40)
    cache.set(_last_refresh_key(event.id), datetime.now(tz=timezone.utc).isoformat(),
              timeout=60 * 60 * 24)

    refreshed = Event.objects.filter(pk=event.id).first() or event
    return OddsFetchResult(
        event=refreshed,
        stale=False,
        markets_ingested=sum(len(m.selections) for m in spec.markets),
        calls_this_month=used + 1,
    )
