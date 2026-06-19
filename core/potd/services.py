"""Pick-of-the-Day curation (plan Phase 6).

Nightly: choose the day's most prominent fixture from the aggregator
catalog and mirror it locally. Heuristic = highest-profile league first
(``POTD_FEATURED_LEAGUES`` ranking, optional), then kickoff closest to
prime time (19:00 NY). Admin can pre-create (or replace) the row — the
cron never overwrites a ``manually_curated`` day.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from core.potd.models import POTD_TZ, PickOfDay, potd_today

logger = logging.getLogger(__name__)

PRIME_TIME_HOUR = 19  # 7pm NY — "the game everyone's watching tonight"


class CurationError(Exception):
    """Curation could not produce a PickOfDay (empty slate, catalog down)."""


def _day_bounds_utc(date):
    start = datetime.combine(date, time.min, tzinfo=POTD_TZ)
    return start, start + timedelta(days=1)


def _league_rank(item) -> int:
    """Position in the featured-league ranking; unlisted leagues sort last.
    ``POTD_FEATURED_LEAGUES`` is an ordered list of aggregator league ids."""
    featured = getattr(settings, "POTD_FEATURED_LEAGUES", []) or []
    league_id = ((item.get("league") or {}).get("id")) or ""
    try:
        return featured.index(league_id)
    except ValueError:
        return len(featured)


def _moneyline_market(item):
    """The FULL_GAME MONEYLINE market dict with its priced selections, or
    None. A 2-way (US sports) or 3-way (soccer: HOME/DRAW/AWAY) market both
    qualify — every priced selection becomes a pickable card option."""
    for market in (item.get("markets") or []):
        if market.get("category") != "MONEYLINE":
            continue
        if market.get("scope") not in (None, "FULL_GAME"):
            continue
        priced = [
            s for s in (market.get("selections") or [])
            if s.get("decimal_odds") is not None
        ]
        if priced:
            return {**market, "selections": priced}
    return None


def pick_candidate(items, *, date):
    """Pure heuristic over an aggregator listing: returns
    ``(event_id, market_dict, start_time)`` of the most prominent fixture
    with a priced moneyline, or None. The market dict carries every priced
    selection so curation can mirror the FULL market locally — the card
    renders from local rows, and a missing side would be unpickable."""
    prime = datetime.combine(date, time(hour=PRIME_TIME_HOUR), tzinfo=POTD_TZ)
    best = None
    best_key = None
    for item in items:
        market = _moneyline_market(item)
        if market is None:
            continue
        start_raw = item.get("start_time")
        start = parse_datetime(start_raw) if isinstance(start_raw, str) else start_raw
        if start is None:
            continue
        key = (_league_rank(item), abs((start - prime).total_seconds()), start)
        if best_key is None or key < best_key:
            best, best_key = (item["id"], market, start), key
    return best


def curate_pick_of_day(date=None):
    """Create (or return) the PickOfDay for ``date`` (default: NY today).

    Idempotent: an existing row — cron- or admin-created — is returned
    untouched. Raises CurationError when nothing viable exists, so the
    task's retry strategy gets a real failure to chew on.
    """
    from core.event.providers.aggregator_client import (
        AggrigatorClient,
        AggrigatorError,
    )
    from core.event.services.aggregator_chain import ChainBuildError, ensure_chain

    date = date or potd_today()
    existing = PickOfDay.objects.for_date(date)
    if existing is not None:
        return existing

    window_start, window_end = _day_bounds_utc(date)
    # Don't curate an event that already kicked off.
    window_start = max(window_start, timezone.now())

    try:
        body = AggrigatorClient().list_events(
            starts_after=window_start.isoformat(),
            starts_before=window_end.isoformat(),
            include="markets",
            page_size=50,
        )
    except AggrigatorError as exc:
        raise CurationError(f"events catalog unreachable: {exc}") from exc

    candidate = pick_candidate(body.get("items") or [], date=date)
    if candidate is None:
        raise CurationError(f"no viable fixture with a priced moneyline on {date}")
    event_id, market, start = candidate

    # Mirror EVERY priced selection of the chosen market — the dashboard
    # card renders from local rows, so each side (incl. DRAW on 3-way
    # soccer moneylines) must exist locally to be pickable.
    selection = None
    try:
        for sel in market["selections"]:
            mirrored = ensure_chain(event_id, sel["id"])
            selection = selection or mirrored
    except ChainBuildError as exc:
        raise CurationError(f"couldn't mirror {event_id} locally: {exc}") from exc

    potd = PickOfDay.objects.create(
        date=date,
        event=selection.market.event,
        market=selection.market,
        lock_time=selection.market.event.start_time or start,
    )
    logger.info("PotD curated for %s: event=%s market=%s (%d selections)",
                date, event_id, selection.market_id, len(market["selections"]))

    _schedule_closing_nudge(potd)
    return potd


def _schedule_closing_nudge(potd):
    """One-shot 'closes in 2h' nudge (Phase 7 schedule_at pattern). The
    queueing lock makes re-curation/re-runs idempotent."""
    from procrastinate import exceptions as procrastinate_exceptions

    from core.potd.tasks import potd_closing_nudge

    nudge_at = potd.lock_time - timedelta(hours=2)
    if nudge_at <= timezone.now():
        return
    from django.db import transaction
    try:
        # Savepoint so the queueing-lock unique violation can't poison a
        # caller's open transaction (same trick as Emails._notify).
        with transaction.atomic():
            potd_closing_nudge.configure(
                queueing_lock=f"potd-nudge-{potd.date}",
                schedule_at=nudge_at,
            ).defer(potd_id=str(potd.pk))
    except procrastinate_exceptions.AlreadyEnqueued:
        pass


def send_closing_nudge(potd_id):
    """Task body: nudge users whose streak is on the line — picked
    yesterday, haven't picked today. In-app always; email only if opted in
    (``Emails._notify`` handles the gate)."""
    from django.contrib.auth import get_user_model

    from core.mail.models import Emails

    potd = PickOfDay.objects.select_related(
        "event", "event__home_team", "event__away_team",
    ).filter(pk=potd_id).first()
    if potd is None or potd.is_locked:
        return 0

    User = get_user_model()
    at_risk = User.objects.filter(
        potd_last_pick_date=potd.date - timedelta(days=1),
        is_active=True,
    ).exclude(daily_picks__potd=potd)

    sent = 0
    for user in at_risk.iterator():
        Emails.send_potd_closing_nudge(user, potd)
        sent += 1
    logger.info("PotD nudge for %s sent to %d users", potd.date, sent)
    return sent
