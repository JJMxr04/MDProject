"""Celery tasks (post-aggregator cutover).

Event ingestion, odds refresh, and settlement moved to the aggregator service
(see ``aggrigator-plan/plan/plan.md`` §7.1). This module now only carries the
match/tournament tasks MDProject still owns.

Removed in the cutover:
- ``event_cron`` / ``live_events_cron``  → aggregator's ``ingest_due_leagues``
- ``warm_upcoming_odds_cron``            → aggregator on-demand refresh
- ``settle_pending_cron``                → aggregator nightly backfill

The legacy SGO ingestion modules (``core.event.sportsgameodds``,
``core.event.crons.eventUpdate``, ``core.event.odds.sgo_*``,
``core.event.odds.service``, ``core.event.odds.settlement``) remain on disk
during the dual-write phase (plan §9 phase 2). Phase 4 cleanup deletes them.
"""

from __future__ import annotations

import logging

from celery import shared_task

from core.match.crons.matchUpdate import MatchCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder

logger = logging.getLogger(__name__)


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
