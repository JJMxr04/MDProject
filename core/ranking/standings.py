"""Leaderboard queries (phase 8 increment 4).

Season standings are points-ordered with the D-8 tiebreakers; a live season
ranks on the fly, a closed one renders from the frozen ``final_rank``. The
global board is the career-points sum. An eligibility floor keeps a single
lucky match from squatting at #1.
"""

from __future__ import annotations

from core.ranking import constants
from core.ranking.models import PlayerProgress, Season, SeasonParticipation


def _season_sort_key(p: SeasonParticipation):
    # season points → win rate → wins → fewer games (D-8).
    return (-p.season_points, -p.win_rate, -p.wins, p.games_played)


def season_leaderboard(season: Season, division: int | None = None) -> list[dict]:
    """Ranked rows for one season (optionally one division). Closed seasons
    use the frozen ``final_rank``; live seasons rank live. Only participants
    past the games floor appear."""
    qs = (
        SeasonParticipation.objects.filter(season=season)
        .select_related("user")
        .filter(games_played__gte=constants.SEASON_ELIGIBILITY_FLOOR)
    )
    if division is not None:
        qs = qs.filter(division=division)

    if season.status == Season.Status.CLOSED:
        rows = list(qs.exclude(final_rank__isnull=True).order_by("division", "final_rank"))
        return [_season_row(p, p.final_rank) for p in rows]

    rows = sorted(qs, key=_season_sort_key)
    return [_season_row(p, rank) for rank, p in enumerate(rows, start=1)]


def season_divisions(season: Season) -> list[int]:
    return sorted(
        SeasonParticipation.objects.filter(season=season)
        .values_list("division", flat=True)
        .distinct()
    )


def global_leaderboard(limit: int = 100) -> list[dict]:
    """Career standings, ordered by global points (tiebreak lifetime win rate
    → wins)."""
    rows = list(
        PlayerProgress.objects.select_related("user")
        .order_by("-global_points", "-lifetime_wins")[:limit]
    )
    out = []
    for rank, p in enumerate(rows, start=1):
        games = p.lifetime_games or 0
        out.append({
            "rank": rank,
            "user": p.user,
            "level": p.level,
            "global_points": p.global_points,
            "wins": p.lifetime_wins,
            "losses": p.lifetime_losses,
            "win_rate": (p.lifetime_wins / games) if games else 0.0,
            "badges": p.user.badges.count(),
        })
    return out


def progress_card_context(user) -> dict:
    """Dashboard widget data: level + XP bar + season rank. Returns
    ``{"rank_progress": None}`` for a player who hasn't earned anything yet."""
    prog = PlayerProgress.objects.filter(user=user).first()
    if prog is None:
        return {"rank_progress": None}

    season = Season.active()
    season_rank = None
    season_points = None
    if season is not None:
        sp = SeasonParticipation.objects.filter(user=user, season=season).first()
        if sp is not None:
            season_points = sp.season_points
            if sp.games_played >= constants.SEASON_ELIGIBILITY_FLOOR:
                for row in season_leaderboard(season, sp.division):
                    if row["user"].pk == user.pk:
                        season_rank = row["rank"]
                        break

    # XP earned in the last 7 days (the ledger makes this exact; points aren't
    # ledgered, so "this week" is XP).
    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from core.ranking.models import XpEvent

    week_ago = timezone.now() - timedelta(days=7)
    xp_week = (
        XpEvent.objects.filter(user=user, created_at__gte=week_ago)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    span = prog.xp_for_next_level or 1
    into = max(0, prog.xp_into_level)
    return {"rank_progress": {
        "level": prog.level,
        "xp_into": into,
        "xp_span": span,
        "xp_pct": min(100, round(into / span * 100)),
        "global_points": prog.global_points,
        "season_rank": season_rank,
        "season_points": season_points,
        "xp_this_week": xp_week,
    }}


def _season_row(p: SeasonParticipation, rank: int) -> dict:
    return {
        "rank": rank,
        "user": p.user,
        "division": p.division,
        "season_points": p.season_points,
        "wins": p.wins,
        "losses": p.losses,
        "draws": p.draws,
        "win_rate": p.win_rate,
        "potd_wins": p.potd_wins,
    }
