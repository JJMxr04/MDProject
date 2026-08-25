"""Match-domain Procrastinate tasks.

"Match settles tonight" — a one-shot scheduled at ``end_date - N hours``
when the match is accepted. Uses the format-aware end_date:
a Blitz accepted Friday fires Sunday afternoon, which is the point.

Auto-discovered via procrastinate's Django integration (installed-app
``tasks.py``).
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from procrastinate import RetryStrategy
from procrastinate import exceptions as procrastinate_exceptions
from procrastinate.contrib.django import app

logger = logging.getLogger(__name__)


@app.task(name="core.match.settles_tonight", queue="default",
          retry=RetryStrategy(max_attempts=2, linear_wait=120))
def match_settles_tonight(match_id: str):
    """Execution-time guards: a match that already
    completed — or never got an opponent — sends nothing."""
    from core.mail.models import Emails
    from core.match.models import Match

    match = (
        Match.objects.select_related("player_1", "player_2")
        .filter(pk=match_id)
        .first()
    )
    if match is None or match.match_state == "completed" or match.player_2 is None:
        return 0

    Emails.send_match_settles_tonight(
        match.player_1, match.player_2.username, match_id=match.id,
    )
    Emails.send_match_settles_tonight(
        match.player_2, match.player_1.username, match_id=match.id,
    )
    return 2


def schedule_settles_tonight(match) -> bool:
    """Defer the one-shot at ``end_date - MATCH_SETTLES_SOON_HOURS``.
    Called from ``accept_match`` — inside its transaction, so the job row
    rolls back with a failed accept. The queueing lock absorbs re-accepts/
    re-schedules; a window too short to warn about schedules nothing."""
    if not match.end_date:
        return False
    from django.utils import timezone

    hours = getattr(settings, "MATCH_SETTLES_SOON_HOURS", 6)
    notify_at = match.end_date - timedelta(hours=hours)
    if notify_at <= timezone.now():
        return False
    from django.db import transaction
    try:
        # Savepoint so the queueing-lock unique violation can't poison a
        # caller's open transaction (same trick as Emails._notify).
        with transaction.atomic():
            match_settles_tonight.configure(
                queueing_lock=f"settles-tonight-{match.pk}",
                schedule_at=notify_at,
            ).defer(match_id=str(match.pk))
        return True
    except procrastinate_exceptions.AlreadyEnqueued:
        return False
