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

    # Catalog of pickable events for this match's window. Source-of-truth is
    # the aggregator (when USE_AGGRIGATOR=True) — see plan §2.4.2 and
    # core/match/views/available_events.py for the proxy + cache layer.
    from core.match.views.available_events import build_available_events
    events_ser = build_available_events(match)

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
    """Pick-submit endpoint. After cutover (plan §2.4.3) the chain
    (Sport→League→Team→Event→Market→Selection + per-book quotes) is fetched
    from the aggregator *first* — never trust the client's odds value — then
    ``Match.objects.upload_pick`` links the Selection to the user's empty
    Game slot via Bet.owner_outcome (or Bet.player_2_outcome for opponent
    picks)."""
    from core.event.services.aggregator_chain import ChainBuildError, ensure_chain

    match = get_object_or_404(Match, id=match_id)
    data = json.loads(request.body)
    event_id = data.get('event_id')
    selection_id = data.get('player_choice')
    if not event_id or not selection_id:
        return JsonResponse(
            {'status': 'error', 'message': 'event_id and player_choice required'},
            status=400,
        )

    try:
        ensure_chain(event_id, selection_id)
    except ChainBuildError as exc:
        # Aggregator unreachable, or the (event, selection) pair the user
        # submitted doesn't exist in the aggregator's catalog. Reject the
        # pick — never persist a half-built chain.
        return JsonResponse(
            {'status': 'error', 'message': f'Catalog unavailable: {exc}'},
            status=400,
        )

    try:
        game = Match.objects.upload_pick(match=match, player=request.user, data=data)
    except PickError as exc:
        # Validation failure from Game.upload_pick (no empty slot, deadline
        # missed, duplicate market on this match, etc.). Surface the message
        # to the popup so the user knows why it didn't take.
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    return JsonResponse({
        'status': 'success',
        'game_id': str(game.id),
    })


@require_POST
@login_required(login_url='/auth/login/')
def player_2_select_outcome(request, game_id):
    from core.event.services.aggregator_chain import ChainBuildError, ensure_chain

    try:
        game = Game.objects.get(id=game_id)
    except Game.DoesNotExist:
        return render(request, '404.html', status=404)
    except ValueError:
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid game ID format'}, status=400,
        )

    data = json.loads(request.body)
    user = request.user

    event_id = data.get("event_id") or (game.event_id if game.event else None)
    selection_id = data.get("player_choice")
    if not event_id or not selection_id:
        return JsonResponse(
            {'status': 'error', 'message': 'event_id and player_choice required'},
            status=400,
        )

    try:
        ensure_chain(event_id, selection_id)
    except ChainBuildError as exc:
        return JsonResponse(
            {'status': 'error', 'message': f'Catalog unavailable: {exc}'},
            status=400,
        )

    try:
        Game.objects.upload_pick(
            current_user=user, match=game.match,
            event_id=event_id, selection_id=selection_id,
        )
        return JsonResponse({'status': 'success'})
    except PickError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
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
    
