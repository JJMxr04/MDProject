from functools import wraps

from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from core.game.models import Game
from core.match.models import Match


def player_in_match_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, match_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'User not authenticated'}, status=401)

        match = get_object_or_404(Match, id=match_id)
        if request.user != match.player_1 and request.user != match.player_2:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized user'}, status=403)
        return view_func(request, match_id, *args, **kwargs)
    return _wrapped_view

def player_in_game_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, game_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'User not authenticated'}, status=401)

        game = get_object_or_404(
            Game.objects.select_related('match__player_1', 'match__player_2'),
            id=game_id,
        )
        # Deny unless the requester is one of the two players on this game's
        # match. Checked via the match (not game.owner/player_2) because the
        # Golden Game is ownerless — both FKs are NULL there; for regular
        # slots owner/player_2 are always the match players anyway.
        if request.user != game.match.player_1 and request.user != game.match.player_2:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized user'}, status=403)
        return view_func(request, game_id, *args, **kwargs)
    return _wrapped_view
