import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from core.event.crons.eventUpdate import EventCron
from core.event.models import Event
from core.event.odds.service import PER_EVENT_MONTHLY_CAP, get_event_odds
from core.event.odds.settlement import settle_pending_events
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


# Hybrid odds strategy. The lazy on-demand fetch in core.event.odds.service
# stays in place — this cron just *opportunistically* warms odds for a small
# slice of relevant events so the upcoming-events page isn't empty until a
# user clicks something.
#
# Quota safety: get_event_odds() enforces:
#   • per-event monthly cap (PER_EVENT_MONTHLY_CAP, default 10)
#   • cache TTL (skips refetch if recently fetched)
# So calling this every 6h won't blow the budget even if the limit is small —
# already-warm events become no-ops, capped events become no-ops, and only
# stale/new events trigger a real call.
WARM_AHEAD_HOURS = 48     # only warm events starting within next 48h
WARM_LIVE_GRACE_HOURS = 4  # also warm events that started up to 4h ago and are still live
WARM_BATCH_SIZE = 10       # max events touched per tick


@shared_task
def warm_upcoming_odds_cron():
    """Opportunistically pre-fetch odds for the next handful of relevant
    events. Returns a small report dict for log/metrics inspection."""
    now = timezone.now()
    horizon = now + timedelta(hours=WARM_AHEAD_HOURS)
    grace = now - timedelta(hours=WARM_LIVE_GRACE_HOURS)

    candidates = (
        Event.objects
        .filter(completed=False)
        .filter(
            Q(status_type="inprogress", start_time__gte=grace)
            | Q(start_time__gte=now, start_time__lte=horizon)
        )
        .order_by("start_time")[:WARM_BATCH_SIZE]
    )

    report = {"considered": 0, "ingested": 0, "stale": 0, "cap_hit": 0}
    for event in candidates:
        report["considered"] += 1
        result = get_event_odds(event)
        if result.markets_ingested > 0:
            report["ingested"] += 1
        if result.stale:
            report["stale"] += 1
        if result.calls_this_month >= PER_EVENT_MONTHLY_CAP:
            report["cap_hit"] += 1

    logger.info("warm_upcoming_odds_cron report: %s", report)
    return report
