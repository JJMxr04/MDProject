"""Procrastinate tasks (post-Celery cutover).

Event ingestion, odds refresh, and settlement moved to the aggregator service
(see ``aggrigator-plan/plan/plan.md`` §7.1). This module now only carries the
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
during the dual-write phase (plan §9 phase 2). Phase 4 cleanup deletes them.
"""

from __future__ import annotations

import logging

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


# All three crons fire at midnight America/New_York. Procrastinate's @periodic
# is in UTC by default; PROCRASTINATE_TIMEZONE in settings shifts that. The
# cron expression "0 0 * * *" matches the previous Celery schedule (daily @
# 00:00 NY time). `pass_context=False` because none of these need job metadata.
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
    """Flip overdue ``sent`` invites to ``expired`` (plan Phase 4 §2).

    The accept path also checks expiry lazily, so this is list-view
    bookkeeping, not the correctness gate — a missed run can't let a stale
    invite through.
    """
    from core.mail.models import Invite

    flipped = Invite.objects.expire_stale()
    if flipped:
        logger.info("expire_invites_cron: flipped %d invites to expired", flipped)


# Season lifecycle (roadmap Phase 8): close ended seasons (freeze final_rank,
# award badges + finish bonuses, apply promotion/relegation), activate the next
# DRAFT, warn when none is scheduled. Daily at midnight NY like the rest.
@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.season_lifecycle_cron", queue="default", retry=CRON_RETRY)
def season_lifecycle_cron(timestamp: int):
    from core.ranking.lifecycle import run_lifecycle

    report = run_lifecycle()
    if report.get("closed") or report.get("activated"):
        logger.info("season_lifecycle_cron: %s", report)
