"""Sync team display data (names + colors + stat_entity_id) from the
aggregator into MDProject's Team rows (design §4).

Update-only: a team present upstream but absent locally is skipped (it
enters via the event webhook, then later syncs refresh it). Full overwrite
of the 8 syncable fields — including setting null when the aggregator has
null. FK/public_id/logo are never touched.
"""

from __future__ import annotations

import logging

from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from core.event.models import Team
from core.event.providers.aggregator_client import AggrigatorClient

logger = logging.getLogger(__name__)

TEAM_SYNC_PAGE_SIZE = 200

SYNC_FIELDS = (
    "name_long", "name_medium", "name_short",
    "primary_color", "secondary_color", "primary_contrast", "secondary_contrast",
    "stat_entity_id",
)


def run_sync_team_data() -> int:
    """Page through the aggregator's /v1/teams and overwrite the syncable
    fields on every MDProject team we already have. Returns count updated."""
    client = AggrigatorClient()
    page, pages, updated = 1, 1, 0
    while page <= pages:
        body = client.list_teams(page=page, page_size=TEAM_SYNC_PAGE_SIZE)
        pages = body.get("pages") or 1
        items = {it["id"]: it for it in (body.get("items") or [])}
        if items:
            rows = list(
                Team.objects.filter(id__in=items.keys()).only("id", *SYNC_FIELDS)
            )
            for t in rows:
                it = items[t.id]
                t.name_long = (it.get("name_long") or "")[:128]
                t.name_medium = (it.get("name_medium") or "")[:64]
                t.name_short = (it.get("name_short") or "")[:32]
                t.primary_color = it.get("primary_color")
                t.secondary_color = it.get("secondary_color")
                t.primary_contrast = it.get("primary_contrast")
                t.secondary_contrast = it.get("secondary_contrast")
                t.stat_entity_id = (it.get("stat_entity_id") or "")[:8]
            Team.objects.bulk_update(rows, list(SYNC_FIELDS), batch_size=500)
            updated += len(rows)
        page += 1
    logger.info("sync_team_data: updated=%d across %d page(s)", updated, pages)
    return updated


@app.task(
    name="core.event.sync_team_data",
    queue="default",
    retry=RetryStrategy(max_attempts=2, linear_wait=120),
)
def sync_team_data_task():
    return run_sync_team_data()


@app.periodic(cron="0 5 * * *")
@app.task(name="core.event.sync_team_data_cron", queue="default")
def sync_team_data_cron(timestamp: int):
    return run_sync_team_data()
