from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.models import Match
from core.event.models import Event
from core.game.models import Game
from django.contrib.auth.decorators import login_required


@login_required(login_url='/auth/login/')
def my_match_detail_view(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    is_player_in_match = request.user.id in [match.player_1.id, match.player_2.id]

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
        'player_1_games': match.player_1_games.all(),
        'player_2_games': match.player_2_games.all(),
    }
    return render(request, 'portal/match/my_match_detail.html', context)
