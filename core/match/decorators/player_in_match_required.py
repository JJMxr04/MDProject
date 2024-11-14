from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from functools import wraps
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