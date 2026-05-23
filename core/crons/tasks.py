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

from procrastinate.contrib.django import app

from core.match.crons.matchUpdate import MatchCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder

logger = logging.getLogger(__name__)


matchCron = MatchCron()
tournament2DayReminder = Tournament2DayReminder()
bracketMaker = BracketMaker()


# All three crons fire at midnight America/New_York. Procrastinate's @periodic
# is in UTC by default; PROCRASTINATE_TIMEZONE in settings shifts that. The
# cron expression "0 0 * * *" matches the previous Celery schedule (daily @
# 00:00 NY time). `pass_context=False` because none of these need job metadata.
@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.complete_matches_cron", queue="default")
def complete_matches_cron(timestamp: int):
    matchCron.completeMatches()


@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.tournament_cron_bracketMaker", queue="default")
def tournament_cron_bracketMaker(timestamp: int):
    bracketMaker.create_brackets()


@app.periodic(cron="0 0 * * *")
@app.task(name="core.crons.tournament_cron_2_day_reminder", queue="default")
def tournament_cron_2_day_reminder(timestamp: int):
    tournament2DayReminder.get_tournments_send_player_email()
