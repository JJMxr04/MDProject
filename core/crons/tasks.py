import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from core.event.crons.eventUpdate import EventCron
from core.event.models import Event
from core.event.models.odds.market import Market
from core.event.odds.service import PER_EVENT_MONTHLY_CAP, get_event_odds
from core.event.odds.settlement import settle_pending_events
from core.event.providers import QuotaExceeded
from core.event.sportsgameodds import (
    MONTHLY_ENTITY_CAP,
    SportsGameOddsClient,
)
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
    """Per-league event ingest. Each active League's cadence determines
    whether this tick fetches; the outer beat fires every couple of hours."""
    eventCron.update_due_leagues()


@shared_task
def live_events_cron():
    """Tight live-only sweep — only events flagged ``status.live=true``."""
    eventCron.ingest_live()


@shared_task
def settle_pending_cron():
    return settle_pending_events(lookback_hours=48)


@shared_task
def print_cron_jobs():
    print("Scheduled and print cron job completed")


# ── Odds warmer ─────────────────────────────────────────────────────────
#
# Prefetches odds for events likely to be opened soon. SGO's per-event call
# cost is one entity, so this loop fans out to N events but stops when:
#   1. Per-event monthly cap is hit (PER_EVENT_MONTHLY_CAP).
#   2. Cache TTL says the row is fresh (no-op fetch).
#   3. The global monthly entity counter (MONTHLY_ENTITY_CAP * 0.95) is hit.
WARM_AHEAD_HOURS = 72
WARM_LIVE_GRACE_HOURS = 6
WARM_BATCH_SIZE = 30
GLOBAL_ENTITY_RESERVE = 100


def _global_entity_remaining() -> int:
    used = SportsGameOddsClient.entities_this_month()
    return max(MONTHLY_ENTITY_CAP - used - GLOBAL_ENTITY_RESERVE, 0)


@shared_task
def warm_upcoming_odds_cron():
    """Pre-fetch odds for upcoming + live events that don't have markets yet.

    Priority order: events WITHOUT markets first (highest payoff), then by
    soonest start time. Stops early if the global entity reserve runs out.
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
        "ingested": 0,
        "skipped_already_db": 0,
        "stale": 0,
        "cap_hit": 0,
        "budget_exhausted": False,
        "global_entities_left_start": _global_entity_remaining(),
    }

    for event in candidates:
        if _global_entity_remaining() <= 0:
            report["budget_exhausted"] = True
            logger.warning(
                "warm_upcoming_odds_cron stopping early: global entity reserve hit"
            )
            break
        report["considered"] += 1
        try:
            result = get_event_odds(event)
        except QuotaExceeded:
            report["budget_exhausted"] = True
            break
        if result.calls_this_month >= PER_EVENT_MONTHLY_CAP:
            report["cap_hit"] += 1
            continue
        if result.stale:
            report["stale"] += 1
            continue
        if result.markets_ingested > 0:
            report["ingested"] += 1
        else:
            report["skipped_already_db"] += 1

    report["global_entities_left_end"] = _global_entity_remaining()
    logger.info("warm_upcoming_odds_cron report: %s", report)
    return report
