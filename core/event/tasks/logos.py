"""Mirror a team crest from the aggregator into MDProject's TeamLogo."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from core.event.models import Team, TeamLogo
from core.event.providers.aggregator_client import AggrigatorClient

logger = logging.getLogger(__name__)

LOGO_MISS_COOLDOWN = timedelta(days=30)


def fetch_team_logo(team_id: str) -> str:
    """Get-or-create the logo bytes for ``team_id``. Returns the resulting
    status string. Idempotent: an ok row, or a missing row inside its
    cooldown, short-circuits without an aggregator call."""
    existing = TeamLogo.objects.filter(pk=team_id).first()
    if existing is not None:
        if existing.status == "ok":
            return "ok"
        if (
            existing.status == "missing"
            and timezone.now() - existing.fetched < LOGO_MISS_COOLDOWN
        ):
            return "missing"

    if not Team.objects.filter(pk=team_id).exists():
        return "team_not_found"

    result = AggrigatorClient().get_team_logo_bytes(team_id)
    if result is None:
        TeamLogo.objects.update_or_create(
            pk=team_id,
            defaults={
                "image": None, "content_type": None, "byte_size": 0,
                "etag": None, "status": "missing", "source": "aggregator",
            },
        )
        logger.info("logo: team=%s -> missing (aggregator 404)", team_id)
        return "missing"

    data, content_type, etag = result
    TeamLogo.objects.update_or_create(
        pk=team_id,
        defaults={
            "image": data, "content_type": content_type,
            "byte_size": len(data),
            "etag": (etag or "").strip('"') or None,
            "status": "ok", "source": "aggregator",
        },
    )
    logger.info("logo: team=%s -> ok (%d bytes)", team_id, len(data))
    return "ok"


@app.task(
    name="core.event.fetch_team_logo",
    queue="default",
    retry=RetryStrategy(max_attempts=3, linear_wait=60),
)
def fetch_team_logo_task(team_id: str):
    return fetch_team_logo(team_id)


def run_backfill_team_logos() -> int:
    """Enqueue a fetch for every team that lacks an ok logo, league by
    league. Returns the number enqueued."""
    from core.event.models import League

    enqueued = 0
    for league_id in League.objects.values_list("id", flat=True).order_by("id"):
        ok_ids = set(
            TeamLogo.objects.filter(team__league_id=league_id, status="ok")
            .values_list("team_id", flat=True)
        )
        team_ids = (
            Team.objects.filter(league_id=league_id)
            .exclude(id__in=ok_ids)
            .values_list("id", flat=True)
        )
        for team_id in team_ids:
            fetch_team_logo_task.defer(team_id=team_id)
            enqueued += 1
    logger.info("backfill_team_logos: enqueued=%d", enqueued)
    return enqueued


@app.periodic(cron="30 4 * * *")
@app.task(
    name="core.event.backfill_team_logos",
    queue="default",
    retry=RetryStrategy(max_attempts=2, linear_wait=120),
)
def backfill_team_logos_cron(timestamp: int):
    return run_backfill_team_logos()
