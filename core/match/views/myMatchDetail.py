from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.models import Match, TieBreaker
from core.match.serializers.match import MatchSerializer
from core.game.models import Game
from core.game.models.game import PickError
from core.event.models import Event
from core.event.serializers.event import EventSerializer, EventWithMarketsSerializer
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
import json
from django.utils import timezone

from datetime import datetime, timedelta
import pytz  # Make sure to import pytz for timezone handling

import uuid

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from core.match.serializers.match import MatchSerializer
from core.event.serializers.event import EventSerializer
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import json

from core.match.decorators import player_in_match_required, player_in_game_required

@login_required(login_url='/auth/login/')
@player_in_match_required
def my_match_detail_view(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    is_player_in_match = match.player_2 is not None and request.user.id in [
        match.player_1.id,
        match.player_2.id,
    ]

    # Events at least 8 hours out, before match end_date, not yet completed
    cutoff = timezone.now() + timedelta(hours=8)
    if match.end_date:
        events = Event.objects.filter(
            start_time__gte=cutoff,
            start_time__lte=match.end_date,
            completed=False,
        ).select_related("sport", "home_team", "away_team").order_by("start_time")
    else:
        events = Event.objects.none()

    events_ser = EventSerializer(events, many=True).data if events else []

    player_1_games = list(match.regular_games_for(match.player_1)) if match.player_1 else []
    player_2_games = (
        list(match.regular_games_for(match.player_2)) if match.player_2 else []
    )

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
        'available_events': events_ser,
        'player_1_games': player_1_games,
        'player_2_games': player_2_games,
    }

    return render(request, 'portal/match/my_match_detail.html', context)


@require_POST
@login_required(login_url='/auth/login/')
@player_in_match_required
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
    
@require_POST
@login_required(login_url='/auth/login/')
# @player_in_game_required
def player_2_select_outcome(request, game_id):
    
    try:
        # Convert game_id to UUID
        
        # Attempt to retrieve the game object using get()
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        # Log the error if game is not found and return 404
        print(f"Game with id {game_id} not found.")
        return render(request, '404.html', status=404)  # Render your 404 page
    except ValueError as ve:
        # Log the error if game_id is not a valid UUID
        print(f"Invalid UUID format for game_id {game_id}: {ve}")
        return JsonResponse({'status': 'error', 'message': 'Invalid game ID format'}, status=400)
    except Exception as e:
        # Log any other errors
        print(f"Error retrieving game with id {game_id}: {e}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
    
    data = json.loads(request.body)
    user = request.user

    try:
        Game.objects.upload_pick(
            current_user=user,
            match=game.match,
            event_id=data.get("event_id") or (game.event_id if game.event else None),
            selection_id=data.get("player_choice"),
        )
        return JsonResponse({'status': 'success'})
    except PickError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        print(f"Error updating game with id {game_id}: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    

@require_POST
@login_required(login_url='/auth/login/')
@player_in_match_required
def upload_tiebreaker_score(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    print('hitting')

    if match.match_state == 'completed':
        return JsonResponse({'status': 'error', 'message': 'Match Completed'}, status=403)
    
    # Check if the user is one of the players in the match
    if (request.user != match.player_1) and (request.user != match.player_2):
        return JsonResponse({'status': 'error', 'message': 'Unauthorized user'}, status=403)

    data = json.loads(request.body)
    tiebreaker_score = data.get('tiebreaker_score')

    # Validate the tiebreaker score
    if tiebreaker_score is None:
        return JsonResponse({'status': 'error', 'message': 'Tiebreaker score is required'}, status=400)

    try:
        if request.user == match.tiebreaker.golden_game.owner:
            TieBreaker.objects.set_owner_total(tiebreaker=match.tiebreaker,total=tiebreaker_score)
        elif request.user == match.tiebreaker.golden_game.player_2:
            TieBreaker.objects.set_player_2_total(tiebreaker=match.tiebreaker,total=tiebreaker_score)
        # Update the match with the tiebreaker score
        match.save()
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
