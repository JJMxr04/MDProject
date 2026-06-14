"""Progression engine (phase 8): credit points, XP, and Elo at match completion.

Called from ``MatchManager.calculate_winner`` (regular matches) and
``_complete_duel_if_ready`` (duels) — both run inside the row-locked completion
path, so each match is credited exactly once. The ledger guard
(``XpEvent`` for this match) is belt-and-braces against replays.

Three counters move together at one chokepoint: season points (if a season is
active), career global points, and the XP ledger. Elo (seasonal + all-time)
updates too but doesn't order any leaderboard v1. Duels are ladder-exempt
(D-14 #4): XP only, no points, no rating, no W/L on the permanent track.
"""

from __future__ import annotations

from core.ranking import constants
from core.ranking.models import PlayerProgress, Season, SeasonParticipation, XpEvent


# --------------------------------------------------------------- public API


def record_match_result(match) -> None:
    """Credit a completed regular match for both players. Idempotent."""
    p1, p2 = match.player_1, match.player_2
    if p2 is None:
        return
    if XpEvent.objects.filter(match=match, source=XpEvent.Source.MATCH_COMPLETED).exists():
        return  # already credited (replay / double-completion)

    weight = constants.format_weight(match.format)
    season = Season.active()
    prog1, prog2 = _progress(p1), _progress(p2)
    sp1 = _participation(p1, season) if season else None
    sp2 = _participation(p2, season) if season else None

    # Outcome scores (also the Elo result): 1 win, 0 loss, 0.5 draw.
    s1 = 1.0 if match.winner_id == p1.pk else 0.0 if match.winner_id == p2.pk else 0.5
    s2 = 1.0 - s1

    # Elo first, from pre-update ratings (all-time + seasonal, separate pools).
    prog1.all_time_rating, prog2.all_time_rating = _elo_pair(
        prog1.all_time_rating, prog2.all_time_rating, s1, s2,
        _k(prog1.lifetime_games) * weight, _k(prog2.lifetime_games) * weight,
    )
    if sp1 is not None and sp2 is not None:
        sp1.rating, sp2.rating = _elo_pair(
            sp1.rating, sp2.rating, s1, s2,
            _k(sp1.games_played) * weight, _k(sp2.games_played) * weight,
        )

    completion_xp = round(constants.XP_MATCH_COMPLETED_BASE * weight)
    win_bonus_xp = round(completion_xp * constants.XP_MATCH_WIN_BONUS_FRACTION)
    win_pts = round(constants.PTS_MATCH_WIN_BASE * weight)
    draw_pts = round(constants.PTS_MATCH_DRAW_BASE * weight)

    for user, prog, sp, score in ((p1, prog1, sp1, s1), (p2, prog2, sp2, s2)):
        old_level = prog.level
        _award_xp(user, prog, XpEvent.Source.MATCH_COMPLETED, completion_xp, match)
        if score == 1.0:
            _award_xp(user, prog, XpEvent.Source.MATCH_WIN, win_bonus_xp, match)

        _award_points(prog, sp, constants.PTS_MATCH_PARTICIPATION)
        if score == 1.0:
            _award_points(prog, sp, win_pts)
        elif score == 0.5:
            _award_points(prog, sp, draw_pts)

        prog.lifetime_games += 1
        if score == 1.0:
            prog.lifetime_wins += 1
        elif score == 0.0:
            prog.lifetime_losses += 1
        else:
            prog.lifetime_draws += 1
        prog.level = constants.level_for_xp(prog.xp)

        if sp is not None:
            sp.games_played += 1
            if score == 1.0:
                sp.wins += 1
            elif score == 0.0:
                sp.losses += 1
            else:
                sp.draws += 1

        prog.save()
        if sp is not None:
            sp.save()
        _maybe_notify_level_up(user, old_level, prog.level)


def grant_duel_xp(match) -> None:
    """Duels are ladder-exempt: the winner gets a small XP award, nothing
    else (no points, no rating, no permanent W/L). Idempotent; draws award
    nobody (D-14 #2)."""
    if match.winner_id is None:
        return
    if XpEvent.objects.filter(match=match, source=XpEvent.Source.DUEL_WON).exists():
        return
    prog = _progress(match.winner)
    old_level = prog.level
    _award_xp(match.winner, prog, XpEvent.Source.DUEL_WON, constants.XP_DUEL_WON, match)
    prog.level = constants.level_for_xp(prog.xp)
    prog.save()
    _maybe_notify_level_up(match.winner, old_level, prog.level)


# ------------------------------------------------------------- POTD (phase 8)


def record_potd_pick(daily_pick) -> None:
    """Credit making today's pick: participation points + XP, plus a streak
    milestone bonus when the user's current streak crosses 7/30/100. POTD does
    NOT move Elo (no opponent). Idempotent per pick via the ledger."""
    user = daily_pick.user
    if XpEvent.objects.filter(potd_pick=daily_pick, source=XpEvent.Source.POTD_PICK).exists():
        return
    prog = _progress(user)
    season = Season.active()
    sp = _participation(user, season) if season is not None else None
    old_level = prog.level

    _award_xp(user, prog, XpEvent.Source.POTD_PICK, constants.XP_POTD_PICK_MADE, potd_pick=daily_pick)
    _award_points(prog, sp, constants.PTS_POTD_PARTICIPATION)
    if sp is not None:
        sp.potd_picks += 1

    streak_bonus = constants.XP_POTD_STREAK.get(getattr(user, "potd_current_streak", 0))
    if streak_bonus:
        _award_xp(user, prog, XpEvent.Source.POTD_STREAK, streak_bonus, potd_pick=daily_pick)

    prog.level = constants.level_for_xp(prog.xp)
    prog.save()
    if sp is not None:
        sp.save()
    _maybe_notify_level_up(user, old_level, prog.level)


def credit_settled_potd() -> int:
    """Idempotently credit every WON DailyPick that hasn't been credited yet.
    Called from the POTD sync cron after ``sync_pending`` (which bulk-updates
    results without signals). Returns the number credited."""
    from core.potd.models import DailyPick, DailyPickResult

    credited = set(
        XpEvent.objects.filter(
            source=XpEvent.Source.POTD_WIN, potd_pick__isnull=False,
        ).values_list("potd_pick_id", flat=True)
    )
    won = (
        DailyPick.objects.filter(result=DailyPickResult.WON)
        .exclude(id__in=credited)
        .select_related("user")
    )
    n = 0
    for dp in won:
        _credit_potd_win(dp)
        n += 1
    return n


def _credit_potd_win(daily_pick) -> None:
    user = daily_pick.user
    if XpEvent.objects.filter(potd_pick=daily_pick, source=XpEvent.Source.POTD_WIN).exists():
        return
    prog = _progress(user)
    season = Season.active()
    sp = _participation(user, season) if season is not None else None
    old_level = prog.level

    _award_xp(user, prog, XpEvent.Source.POTD_WIN, constants.XP_POTD_PICK_WON, potd_pick=daily_pick)
    _award_points(prog, sp, constants.PTS_POTD_WIN)
    if sp is not None:
        sp.potd_wins += 1

    prog.level = constants.level_for_xp(prog.xp)
    prog.save()
    if sp is not None:
        sp.save()
    _maybe_notify_level_up(user, old_level, prog.level)


# ------------------------------------------------------------- internals


def _progress(user) -> PlayerProgress:
    prog, _ = PlayerProgress.objects.get_or_create(user=user)
    return prog


def _participation(user, season) -> SeasonParticipation:
    sp = SeasonParticipation.objects.filter(user=user, season=season).first()
    if sp is not None:
        return sp
    # Seed the division from the player's standing band (promotion/relegation
    # carries across seasons via PlayerProgress.current_division).
    return SeasonParticipation.objects.create(
        user=user, season=season, division=_progress(user).current_division,
    )


def _award_points(prog, sp, amount) -> None:
    prog.global_points += amount
    if sp is not None:
        sp.season_points += amount


def _award_xp(user, prog, source, amount, match=None, potd_pick=None) -> None:
    if amount <= 0:
        return
    XpEvent.objects.create(
        user=user, source=source, amount=amount, match=match, potd_pick=potd_pick,
    )
    prog.xp += amount


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def _elo_pair(ra, rb, sa, sb, ka, kb):
    return (
        ra + ka * (sa - _expected(ra, rb)),
        rb + kb * (sb - _expected(rb, ra)),
    )


def _k(games_played: int) -> float:
    if games_played < constants.ELO_PROVISIONAL_MATCHES:
        return constants.ELO_K_BASE * constants.ELO_PROVISIONAL_MULTIPLIER
    return float(constants.ELO_K_BASE)


def _maybe_notify_level_up(user, old_level: int, new_level: int) -> None:
    if new_level <= old_level:
        return
    # In-app always (phase 8); milestone-level email is a later increment.
    from core.mail.models.notifications import Notification

    Notification.objects.create_notification(
        user, f"You reached level {new_level}! 🎉",
    )
