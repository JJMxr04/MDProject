from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render

from core.tournament.models import Tournament
from core.tournament.models.tournament import InvitedPlayer, Player


@login_required(login_url='/auth/login/')
def my_tournament_detail(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    user_id = request.user.id

    is_participant = Player.objects.filter(
        player=user_id, tournament=tournament
    ).exists()
    # Staff can view any tournament; participants can view their own.
    if not is_participant and not request.user.is_staff:
        raise PermissionDenied("You are not a player in this tournament.")

    rounds = (
        tournament.rounds.all()
        .select_related('player_1__player', 'player_2__player',
                        'winner__player', 'match')
        .order_by('level_num')
    )

    by_level = defaultdict(list)
    for r in rounds:
        r.winner_is_player_1 = bool(r.winner_id and r.winner_id == r.player_1_id)
        r.winner_is_player_2 = bool(r.winner_id and r.winner_id == r.player_2_id)
        r.is_mine = any(
            p and p.player_id == user_id
            for p in (r.player_1, r.player_2)
        )
        by_level[r.level_num].append(r)
    # Highest level first so the template iterates finals → … → round 1.
    # CSS reverses column order so rendering is first-round-on-left.
    rounds_by_level = sorted(by_level.items(), key=lambda kv: -kv[0])

    accepted_players = Player.objects.filter(
        tournament=tournament
    ).select_related('player')
    invited_players = InvitedPlayer.objects.filter(
        tournament=tournament
    ).select_related('player')

    my_position = _compute_my_position(rounds, user_id) if is_participant else None

    crumbs = [
        {"label": "Tournaments", "href": "/web/portal/tournament/me/"},
        {"label": tournament.name},
    ]

    return render(request, 'portal/tournament/my_tournament_detail.html', {
        'tournament': tournament,
        'rounds_by_level': rounds_by_level,
        'accepted_players': accepted_players,
        'invited_players': invited_players,
        'my_position': my_position,
        'is_participant': is_participant,
        'crumbs': crumbs,
    })


def _compute_my_position(rounds, user_id):
    """Friendly 'You are in …' string, or None."""
    if not rounds:
        return None
    my_rounds = [
        r for r in rounds
        if any(p and p.player_id == user_id for p in (r.player_1, r.player_2))
    ]
    if not my_rounds:
        return None
    # Round with the lowest level_num that I'm still in (0 = final).
    still_alive = [r for r in my_rounds if not r.completed or r.winner_id == user_id]
    if not still_alive:
        # Find the highest level where I lost.
        lost = [r for r in my_rounds if r.completed and r.winner_id != user_id]
        if lost:
            eliminated_at = min(r.level_num for r in lost)
            return f"Eliminated in level {eliminated_at}"
        return "Eliminated"
    level = min(r.level_num for r in still_alive)
    label = {0: "Final", 1: "Semifinal", 2: "Quarterfinal"}.get(level, f"Level {level}")
    return label
