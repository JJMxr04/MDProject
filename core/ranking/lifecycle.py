"""Season lifecycle (phase 8 increment 2): close ended seasons, freeze ranks,
award badges + finish bonuses, apply promotion/relegation, activate the next
season — plus a warning when none is scheduled.

The daily cron (``core.crons.season_lifecycle_cron``) calls ``run_lifecycle``;
the body lives here so it's unit-testable without the scheduler. All money/rank
mutation is idempotent at the season-status level: a season only transitions
ACTIVE → CLOSED once, so re-runs are no-ops.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from core.ranking import constants
from core.ranking.models import Badge, PlayerProgress, Season, SeasonParticipation, XpEvent

logger = logging.getLogger(__name__)


def run_lifecycle(today=None) -> dict:
    """Daily season-lifecycle pass. Returns a small report for logging/tests."""
    today = today or timezone.now().date()
    report = {"closed": [], "activated": [], "warned": False}

    # 1. Close any ACTIVE season whose window has ended.
    for season in Season.objects.filter(status=Season.Status.ACTIVE, end_date__lt=today):
        close_season(season)
        report["closed"].append(season.slug)

    # 2. Activate the next DRAFT whose start has arrived (only if none is live).
    if Season.active() is None:
        nxt = (
            Season.objects.filter(status=Season.Status.DRAFT, start_date__lte=today)
            .order_by("start_date")
            .first()
        )
        if nxt is not None:
            activate_season(nxt)
            report["activated"].append(nxt.slug)

    # 3. Warn (surfaces in GlitchTip) if the live season ends soon and there's
    # no DRAFT queued behind it.
    active = Season.active()
    if active is not None:
        days_left = (active.end_date - today).days
        if days_left <= constants.MISSING_NEXT_SEASON_WARN_DAYS:
            has_next = Season.objects.filter(
                status=Season.Status.DRAFT, start_date__gte=today,
            ).exists()
            if not has_next:
                logger.warning(
                    "No upcoming season scheduled — active %r ends in %d day(s).",
                    active.name, days_left,
                )
                report["warned"] = True
    return report


@transaction.atomic
def close_season(season: Season) -> None:
    """Freeze final ranks, award badges + finish bonuses, reassign divisions."""
    parts = list(SeasonParticipation.objects.filter(season=season).select_related("user"))
    eligible = [p for p in parts if p.games_played >= constants.SEASON_ELIGIBILITY_FLOOR]

    # Rank within each division; freeze final_rank; award the top of each.
    by_division = defaultdict(list)
    for p in eligible:
        by_division[p.division].append(p)
    for members in by_division.values():
        members.sort(key=_standings_key)
        for rank, p in enumerate(members, start=1):
            p.final_rank = rank
            p.save(update_fields=["final_rank"])
            if rank == 1:
                _award_badge(p.user, Badge.Type.DIVISION_WINNER, season)
            if rank <= constants.SEASON_FINISH_TOP_N:
                _award_badge(p.user, Badge.Type.TOP_THREE, season)
                _award_season_finish_bonus(p.user, season)

    # Promotion / relegation: next season's division follows this season's
    # overall standing.
    _reassign_divisions(sorted(eligible, key=_standings_key))

    season.status = Season.Status.CLOSED
    season.save(update_fields=["status"])


def activate_season(season: Season) -> None:
    season.status = Season.Status.ACTIVE
    season.save(update_fields=["status"])
    # Tell engaged players (those with a progress row) the season has begun.
    from core.mail.models import Emails

    for prog in PlayerProgress.objects.select_related("user"):
        Emails.send_season_started(prog.user, season.name)


# ------------------------------------------------------------- internals


def _standings_key(p: SeasonParticipation):
    # Season points first; tiebreakers win rate → wins → fewer games.
    return (-p.season_points, -p.win_rate, -p.wins, p.games_played)


def _award_badge(user, badge_type, season) -> None:
    Badge.objects.get_or_create(user=user, type=badge_type, season=season)


def _award_season_finish_bonus(user, season) -> None:
    # Idempotent at the season level: a season transitions ACTIVE → CLOSED once
    # (run_lifecycle only closes ACTIVE seasons), so this fires once per finish.
    prog, _ = PlayerProgress.objects.get_or_create(user=user)
    prog.global_points += constants.PTS_SEASON_FINISH_TOP3
    XpEvent.objects.create(
        user=user, source=XpEvent.Source.SEASON_FINISH,
        amount=constants.XP_SEASON_TOP3, match=None,
    )
    prog.xp += constants.XP_SEASON_TOP3
    prog.level = constants.level_for_xp(prog.xp)
    prog.save()


def _reassign_divisions(ranked) -> None:
    """Persist next-season divisions on PlayerProgress. Below the split
    threshold everyone stays in division 1; above it, bands of DIVISION_SIZE by
    final standing."""
    n = len(ranked)
    split = n >= constants.DIVISION_SPLIT_THRESHOLD
    for idx, p in enumerate(ranked):
        prog, _ = PlayerProgress.objects.get_or_create(user=p.user)
        prog.current_division = (idx // constants.DIVISION_SIZE) + 1 if split else 1
        prog.save(update_fields=["current_division"])
