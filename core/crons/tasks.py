import logging
from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core.event.crons.eventUpdate import EventCron
from core.event.models import Event
from core.event.models.odds.market import Market
from core.event.odds.normalize import ingest_odds
from core.event.odds.service import (
    PER_EVENT_MONTHLY_CAP,
    _raw_cache_key,
    get_event_odds,
)
from core.event.odds.settlement import settle_pending_events
from core.event.sofascore import MONTHLY_CAP, SofaScoreClient
from core.match.crons.matchUpdate import MatchCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder

logger = logging.getLogger(__name__)


eventCron = EventCron()
matchCron = MatchCron()
tournament2DayReminder = Tournament2DayReminder()
bracketMaker = BracketMaker()


@shared_task
def complete_matches_cron():
    matchCron.completeMatches()


@shared_task
def tournament_cron_bracketMaker():
    bracketMaker.create_brackets()


@shared_task
def tournament_cron_2_day_reminder():
    tournament2DayReminder.get_tournments_send_player_email()


@shared_task
def event_cron():
    eventCron.update_all_events()


@shared_task
def settle_pending_cron():
    return settle_pending_events(lookback_hours=48)


@shared_task
def print_cron_jobs():
    print("Scheduled and print cron job completed")


# ── Odds warmer ─────────────────────────────────────────────────────────
#
# The portal's "Upcoming events" page hides events with no markets, so we
# need odds populated proactively. The lazy on-demand fetch in
# core.event.odds.service still serves any event a user clicks; this task
# rounds out the catalog so the listing is never empty.
#
# Three quota safety nets are stacked on every fetch (in service.py):
#   1. Per-event monthly cap (PER_EVENT_MONTHLY_CAP = 10) — prevents one
#      hot event from eating the whole budget.
#   2. Cache TTL (30s live / 30min near / 6h far) — skips redundant fetches.
#   3. Global monthly cap (sofascore.SOFT_LIMIT = 480 of 500) — hard floor.
#
# Result: calling this every 30 minutes is *safe* — already-fresh events
# become no-ops via cache, capped events become no-ops via per-event guard,
# and the global SOFT_LIMIT is the absolute ceiling.
WARM_AHEAD_HOURS = 168          # one week of upcoming events
WARM_LIVE_GRACE_HOURS = 6        # plus live events that started within last 6h
WARM_BATCH_SIZE = 30             # max events touched per tick
GLOBAL_BUDGET_RESERVE = 30       # leave this many calls/month for everything else


def _global_budget_remaining() -> int:
    """Conservative read of the global monthly counter."""
    used = SofaScoreClient.calls_this_month()
    return max(MONTHLY_CAP - used - GLOBAL_BUDGET_RESERVE, 0)


@shared_task
def warm_upcoming_odds_cron():
    """Pre-fetch odds for upcoming + live events.

    Priority order: events WITHOUT markets first (highest payoff), then by
    soonest start time. Stops early if the global budget runs out.

    Returns a small report dict for log/metrics inspection.
    """
    now = timezone.now()
    horizon = now + timedelta(hours=WARM_AHEAD_HOURS)
    grace = now - timedelta(hours=WARM_LIVE_GRACE_HOURS)

    has_markets = Market.objects.filter(event=OuterRef("pk"))

    candidates = (
        Event.objects
        .filter(completed=False)
        .filter(
            Q(status_type="inprogress", start_time__gte=grace)
            | Q(start_time__gte=now, start_time__lte=horizon)
        )
        .annotate(has_markets=Exists(has_markets))
        # False sorts before True, so "no markets yet" events come first.
        .order_by("has_markets", "start_time")[:WARM_BATCH_SIZE]
    )

    report = {
        "considered": 0,
        "ingested_api": 0,        # real fetch from SofaScore + ingest
        "ingested_from_cache": 0, # repaired DB from already-cached payload (0 API calls)
        "skipped_already_db": 0,  # event had markets in DB AND cache fresh — true no-op
        "stale": 0,
        "cap_hit": 0,
        "budget_exhausted": False,
        "global_budget_left_start": _global_budget_remaining(),
    }

    for event in candidates:
        if _global_budget_remaining() <= 0:
            report["budget_exhausted"] = True
            logger.warning(
                "warm_upcoming_odds_cron stopping early: global budget reserve hit"
            )
            break
        report["considered"] += 1
        outcome = _warm_one_event(event)
        report[outcome] = report.get(outcome, 0) + 1

    report["global_budget_left_end"] = _global_budget_remaining()
    logger.info("warm_upcoming_odds_cron report: %s", report)
    return report


def _warm_one_event(event: Event) -> str:
    """Ensure DB markets exist for a single event. Returns the bucket name."""
    has_db_markets = Market.objects.filter(event=event).exists()

    # Fast path: event already has markets in the DB → normal cache-aware fetch.
    # This refreshes odds when the cache TTL expires, no-ops when fresh.
    if has_db_markets:
        result = get_event_odds(event)
        if result.calls_this_month >= PER_EVENT_MONTHLY_CAP:
            return "cap_hit"
        if result.stale:
            return "stale"
        if result.markets_ingested > 0:
            return "ingested_api"
        return "skipped_already_db"

    # No markets in DB. The service might still hold a cached payload from a
    # previous run (e.g. DB got reset, Redis didn't). Use that payload to
    # re-ingest WITHOUT spending an API call.
    cached = cache.get(_raw_cache_key(event.id))
    payload = cached.get("payload") if isinstance(cached, dict) else None
    if payload:
        try:
            n = ingest_odds(event, payload)
        except Exception:
            logger.exception("ingest_odds from cache failed for event=%s", event.id)
            n = 0
        if n > 0:
            return "ingested_from_cache"
        # cached payload had no usable markets — fall through to a real fetch

    # Cache empty (or its payload had no markets). Force a real API fetch.
    result = get_event_odds(event, force=True)
    if result.calls_this_month >= PER_EVENT_MONTHLY_CAP:
        return "cap_hit"
    if result.stale:
        return "stale"
    if result.markets_ingested > 0:
        return "ingested_api"
    return "stale"  # no markets came back from the API
