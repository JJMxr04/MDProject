from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.match.duels import duel_record
from core.ranking.models import PlayerProgress, Season, SeasonParticipation
from core.ranking.standings import progress_card_context


def _win_rate(wins, losses):
    decided = wins + losses
    return round(100 * wins / decided) if decided else None


@login_required(login_url="/auth/login/")
def portal_stats(request):
    """Consolidated performance stats — the single home for records that used
    to be scattered across the dashboard, duels, etc."""
    user = request.user

    prog = PlayerProgress.objects.filter(user=user).first()
    match_record = None
    if prog is not None:
        match_record = {
            "wins": prog.lifetime_wins,
            "losses": prog.lifetime_losses,
            "draws": prog.lifetime_draws,
            "games": prog.lifetime_games,
            "win_rate": _win_rate(prog.lifetime_wins, prog.lifetime_losses),
        }

    season = Season.active()
    sp = None
    if season is not None:
        sp = SeasonParticipation.objects.filter(user=user, season=season).first()

    season_record = None
    if sp is not None:
        season_record = {
            "wins": sp.wins,
            "losses": sp.losses,
            "draws": sp.draws,
            "games": sp.games_played,
            "points": sp.season_points,
            "division": sp.division,
            "potd_wins": sp.potd_wins,
            "win_rate": _win_rate(sp.wins, sp.losses),
        }

    ctx = {
        **progress_card_context(user),
        "match_record": match_record,
        "duel_stats": duel_record(user),
        "season": season,
        "season_record": season_record,
        "potd_current_streak": getattr(user, "potd_current_streak", 0),
        "potd_best_streak": getattr(user, "potd_best_streak", 0),
    }
    return render(request, "portal/stats/stats.html", ctx)
