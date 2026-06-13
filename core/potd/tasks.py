"""Procrastinate tasks for Pick of the Day (plan Phase 6).

Auto-discovered via procrastinate's Django integration (installed-app
``tasks.py``), same as core.mail.tasks / core.game.tasks.
"""

from __future__ import annotations

import logging

from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

logger = logging.getLogger(__name__)

# Same shape as core/crons/tasks.py CRON_RETRY — a transient catalog blip
# shortly after midnight must not cost the whole day's pick.
CURATION_RETRY = RetryStrategy(max_attempts=5, linear_wait=300)


# 00:10 NY — just after the product-day boundary, before anyone's awake.
@app.periodic(cron="10 0 * * *")
@app.task(name="core.potd.curate_pick_of_day", queue="default", retry=CURATION_RETRY)
def curate_pick_of_day_cron(timestamp: int):
    from core.potd.services import curate_pick_of_day

    potd = curate_pick_of_day()
    logger.info("PotD cron ensured %s", potd)


# Nightly result sync — settlement is inline in the event-upsert path (no
# signal), so PENDING DailyPicks are reconciled here and lazily before
# leaderboard renders.
@app.periodic(cron="30 0 * * *")
@app.task(name="core.potd.sync_results", queue="default",
          retry=RetryStrategy(max_attempts=3, linear_wait=60))
def sync_results_cron(timestamp: int):
    from core.potd.models import DailyPick

    changed = DailyPick.objects.sync_pending()
    if changed:
        logger.info("PotD results synced: %d picks settled", changed)


@app.task(name="core.potd.closing_nudge", queue="default",
          retry=RetryStrategy(max_attempts=2, linear_wait=120))
def potd_closing_nudge(potd_id: str):
    from core.potd.services import send_closing_nudge

    send_closing_nudge(potd_id)
