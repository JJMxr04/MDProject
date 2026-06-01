from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from functools import wraps
from core.match.models import Match
from core.game.models import Game

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
        
        game = get_object_or_404(Game, id=game_id)
        # Deny unless the requester is one of the two players on this game.
        # Was `!= owner OR != player_2`, which is always true (you can't equal
        # both) -> it rejected everyone / was logically broken. Correct guard
        # is: reject if NOT owner AND NOT player_2. See findings.md S-15.
        if request.user != game.owner and request.user != game.player_2:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized user'}, status=403)
        return view_func(request, game_id, *args, **kwargs)
    return _wrapped_view