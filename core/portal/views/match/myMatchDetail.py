from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.models import Match
from core.match.serializers.match import MatchSerializer
from core.event.models import Event
from core.event.serializers.event import EventSerializer, EventBookmakerSerializer
from core.game.models import Game
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
import json
from django.utils import timezone

from datetime import datetime, timedelta



@login_required(login_url='/auth/login/')
def my_match_detail_view(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    is_player_in_match = request.user.id in [match.player_1.id, match.player_2.id]
    events = EventBookmakerSerializer(Event.objects.filter(commence_time__gte=timezone.now() + timedelta(hours=8.25), commence_time__lte=match.end_date), many=True).data

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
        'available_events': events,
        # 'player_1_games': match.player_1_games.all(),
        # 'player_2_games': match.player_2_games.all(),
    }
    
    return render(request, 'portal/match/my_match_detail.html', context)

@require_POST
@login_required(login_url='/auth/login/')
def upload_pick(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    data = json.loads(request.body)
    event_id = data.get('event_id')
    player_choice = data.get('player_choice')

    try:
        Match.objects.upload_pick(match=match, player=request.user, data=data)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
