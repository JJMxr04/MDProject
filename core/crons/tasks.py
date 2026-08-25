"""Procrastinate tasks (post-Celery cutover).

Event ingestion, odds refresh, and settlement moved to the aggregator service.
This module now only carries the
match/tournament tasks MDProject still owns.

Removed in the aggregator cutover:
- ``event_cron`` / ``live_events_cron``  → aggregator's ``ingest_due_leagues``
- ``warm_upcoming_odds_cron``            → aggregator on-demand refresh
- ``settle_pending_cron``                → aggregator nightly backfill

Removed in the Procrastinate cutover:
- Celery imports + ``@shared_task`` decorators.
- ``CELERY_BEAT_SCHEDULE`` in settings — schedules now live next to each
  task via ``@app.periodic(cron=...)``.

The legacy SGO ingestion modules (``core.event.sportsgameodds``,
``core.event.crons.eventUpdate``, ``core.event.odds.sgo_*``,
``core.event.odds.service``, ``core.event.odds.settlement``) remain on disk
during the dual-write phase. A later cleanup pass deletes them.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from core.match.crons.matchUpdate import MatchCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder

logger = logging.getLogger(__name__)


matchCron = MatchCron()
tournament2DayReminder = Tournament2DayReminder()
bracketMaker = BracketMaker()

# A transient failure (DB blip, mail backend hiccup) at midnight would
# otherwise silently skip that day's run — the next periodic defer is 24h
# away. Retry a few times with growing waits before giving up.
CRON_RETRY = RetryStrategy(max_attempts=3, linear_wait=60)


# These crons fire at 00:00 UTC daily. Procrastinate evaluates @app.periodic
# cron expressions in UTC — there is no timezone option (the former
# PROCRASTINATE_TIMEZONE setting was a no-op), so "0 0 * * *" is 00:00 UTC ≈
# 20:00 America/New_York the prior evening, NOT NY midnight. That's acceptable
# here: these tasks key off UTC dates / timezone.now() (TIME_ZONE='UTC'), not an
# NY product-day. A task that needs a true NY wall-clock boundary must bake the
# offset into its cron (see core.potd.tasks → "10 5 * * *" ≈ 00:10 NY).
@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.complete_matches_cron", queue="default", retry=CRON_RETRY)
def complete_matches_cron(timestamp: int):
    matchCron.completeMatches()


@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.tournament_cron_bracketMaker", queue="default", retry=CRON_RETRY)
def tournament_cron_bracketMaker(timestamp: int):
    bracketMaker.create_brackets()


@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.tournament_cron_2_day_reminder", queue="default", retry=CRON_RETRY)
def tournament_cron_2_day_reminder(timestamp: int):
    tournament2DayReminder.get_tournments_send_player_email()


@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.expire_invites_cron", queue="default", retry=CRON_RETRY)
def expire_invites_cron(timestamp: int):
    """Flip overdue ``sent`` invites to ``expired``.

    The accept path also checks expiry lazily, so this is list-view
    bookkeeping, not the correctness gate — a missed run can't let a stale
    invite through.
    """
    from core.mail.models import Invite

    flipped = Invite.objects.expire_stale()
    if flipped:
        logger.info("expire_invites_cron: flipped %d invites to expired", flipped)


# Season lifecycle: close ended seasons (freeze final_rank,
# award badges + finish bonuses, apply promotion/relegation), activate the next
# DRAFT, warn when none is scheduled. Daily at midnight NY like the rest.
@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.season_lifecycle_cron", queue="default", retry=CRON_RETRY)
def season_lifecycle_cron(timestamp: int):
    from core.ranking.lifecycle import run_lifecycle

    report = run_lifecycle()
    if report.get("closed") or report.get("activated"):
        logger.info("season_lifecycle_cron: %s", report)


# Stripe webhooks are the primary subscription-state path, but they can be
# missed (delivery failure, downtime). Since entitlement gates on status, a
# missed cancellation would linger as PRO access. This daily safety net
# re-pulls Stripe's canonical state for locally-active subs and corrects drift.
# Offset to 00:30 NY so it doesn't pile onto the midnight crowd.
@app.periodic(cron="30 0 * * *")
@app.task(name="core.crons.reconcile_subscriptions_cron", queue="default", retry=CRON_RETRY)
def reconcile_subscriptions_cron(timestamp: int):
    from core.billing.services.reconcile import reconcile_subscriptions

    reconcile_subscriptions()


def _purge_login_events_older_than(days: int) -> int:
    """Delete LoginEvent rows older than ``days``. KnownLoginFingerprint is
    intentionally untouched — it's the long-lived detection baseline."""
    from core.auth.models import LoginEvent

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = LoginEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted


@app.periodic(cron="30 3 * * *")
@app.task(name="core.crons.purge_login_events", queue="default", retry=CRON_RETRY)
def purge_login_events(timestamp: int):
    # 90-day retention on detailed login records. Runs 03:30 daily,
    # off-peak and clear of the midnight match/tournament crons.
    count = _purge_login_events_older_than(90)
    logger.info("purge_login_events: deleted %s rows", count)
