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
    # select_related on the Match's FKs — template + decorator both touch
    # player_1/player_2/winner/tiebreaker.golden_game. Without this, each
    # {{ match.player_2.username }} access in the template is one
    # round-trip to Neon. (The golden game is ownerless — its sides are
    # match.player_1/player_2, already selected here.)
    match = get_object_or_404(
        Match.objects
            .select_related(
                "player_1", "player_2", "winner",
                "tiebreaker", "tiebreaker__golden_game",
            ),
        id=match_id,
    )
    is_player_in_match = match.player_2 is not None and request.user.id in [
        match.player_1.id,
        match.player_2.id,
    ]

    # Catalog of pickable events for this match's window. Source-of-truth is
    # the aggregator (when USE_AGGRIGATOR=True) — see plan §2.4.2 and
    # core/match/views/available_events.py for the proxy + cache layer.
    from core.match.views.available_events import build_available_events
    events_ser = build_available_events(match)

    # Each game card in _game_card.html dereferences game.event.{league,
    # sport, home_team, away_team}, game.bet.{owner_outcome,
    # player_2_outcome}, plus game.owner / game.player_2. Without
    # select_related this is ~7 queries per card × 10 cards = ~70 queries.
    games_qs = match.games.select_related(
        "event", "event__league", "event__sport",
        "event__home_team", "event__away_team",
        "bet", "bet__owner_outcome", "bet__player_2_outcome",
        "bet__owner_outcome__market", "bet__locked_market",
        "owner", "player_2",
    )
    player_1_games = (
        list(games_qs.filter(owner=match.player_1, is_golden=False).order_by("slot"))
        if match.player_1 else []
    )
    player_2_games = (
        list(games_qs.filter(owner=match.player_2, is_golden=False).order_by("slot"))
        if match.player_2 else []
    )

    # Fetched once with the card's relations preloaded — the template used
    # to call the ``match.golden_game`` property repeatedly, each access a
    # fresh unjoined query.
    golden_game = games_qs.filter(is_golden=True).first()

    # Rank flair for the match header (phase 8) — level + current-season
    # division for both players, one query each.
    from core.ranking.standings import divisions_for, levels_for
    p2_id = match.player_2_id
    ids = [match.player_1_id, p2_id]
    levels = levels_for(ids)
    divisions = divisions_for(ids)

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
        'available_events': events_ser,
        'player_1_games': player_1_games,
        'player_2_games': player_2_games,
        'golden_game': golden_game,
        'player_1_level': levels.get(match.player_1_id),
        'player_2_level': levels.get(p2_id),
        'player_1_division': divisions.get(match.player_1_id),
        'player_2_division': divisions.get(p2_id),
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
@player_in_game_required
def pick_on_locked_slot(request, game_id):
    """Pick endpoint for slots whose market is pre-locked (Golden Game).

    The popup hits this when ``data.locked_market`` is present in the
    event-markets response. Either player can call it; the manager method
    routes to ``owner_outcome`` (player_1) or ``player_2_outcome``
    (player_2) based on which side the requester is on.
    """
    from core.event.services.aggregator_chain import ChainBuildError, ensure_chain

    try:
        game = Game.objects.select_related('event', 'bet', 'match').get(id=game_id)
    except Game.DoesNotExist:
        return render(request, '404.html', status=404)
    except ValueError:
        return JsonResponse(
            {'status': 'error', 'message': 'Invalid game ID format'}, status=400,
        )

    data = json.loads(request.body)
    selection_id = data.get('player_choice')
    event_id = data.get('event_id') or (game.event_id if game.event else None)
    if not event_id or not selection_id:
        return JsonResponse(
            {'status': 'error', 'message': 'event_id and player_choice required'},
            status=400,
        )

    # Make sure the chosen Selection actually exists locally — picks for
    # locked-market slots usually do (the chain ran at golden-game seed
    # time), but a different selection in the same market might not.
    try:
        ensure_chain(event_id, selection_id)
    except ChainBuildError as exc:
        return JsonResponse(
            {'status': 'error', 'message': f'Catalog unavailable: {exc}'},
            status=400,
        )

    try:
        Game.objects.pick_on_locked_slot(
            current_user=request.user,
            game_id=game_id,
            selection_id=selection_id,
            tiebreaker_total=data.get('tiebreaker_score'),
        )
    except PickError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    return JsonResponse({'status': 'success', 'game_id': str(game.id)})


@require_POST
@login_required(login_url='/auth/login/')
@player_in_game_required
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
def rematch_view(request, match_id):
    """Rematch CTA (Phase 5 §5): two clicks from the completion screen to a
    pre-filled invite — same format, roles swapped (the clicker becomes the
    sender), normal accept flow from there.
    """
    from core.game.models import Game
    from core.game.models.game import FixtureUnavailable
    from core.mail.models import Invite

    match = get_object_or_404(
        Match.objects.select_related("player_1", "player_2"), id=match_id,
    )

    if match.match_state != 'completed':
        return JsonResponse(
            {'status': 'error', 'message': 'You can only rematch a completed match.'},
            status=400,
        )
    if match.player_2 is None:
        return JsonResponse(
            {'status': 'error', 'message': 'This match has no opponent to rematch.'},
            status=400,
        )

    opponent = match.player_2 if request.user == match.player_1 else match.player_1

    # The CTA itself is the loop metric (Phase 3 taxonomy) — fire before
    # the idempotency check so repeat intent still counts.
    from core.metrics.models import track
    track(request.user, "rematch_clicked",
          match_id=str(match.id), format=match.format)

    # One pending *match* challenge per pair — same dedupe as the create view.
    # Duels (per event+market) are independent and must not block a rematch.
    # ``has_key`` avoids the JSON-NULL trap that ``payload__duel=True`` exclude
    # hits for regular match invites (which carry no ``duel`` key).
    existing = Invite.objects.filter(
        sender=request.user, player=opponent, type='match', state='sent',
    ).exclude(payload__has_key='duel').first()
    if existing:
        return JsonResponse({
            'status': 'success', 'invite_id': str(existing.id),
            'message': f'You already have a challenge waiting for {opponent.username}.',
        })

    # Same-format fixture check (D-5 #2) — tonight's rematch needs a
    # viable window right now, not when the original match was created.
    try:
        Game.objects.assert_window_viable(match_format=match.format)
    except FixtureUnavailable as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    invite = Invite.objects.create_invite(
        obj_id=None,
        sender=request.user,
        player=opponent,
        invite_type='match',
        payload={'format': match.format, 'rematch_of': str(match.id)},
    )
    return JsonResponse({
        'status': 'success', 'invite_id': str(invite.id),
        'message': f'Rematch invite sent to {opponent.username}.',
    })

