from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.event.serializers.event import EventSerializer
from core.event.serializers.market import MarketSerializer
from core.event.serializers.selection import SelectionSerializer
from core.game.models import Game
from core.match.decorators import player_in_game_required


@require_GET
@login_required(login_url="/auth/login/")
@player_in_game_required
def event_markets(request, game_id):
    """Return the event the slot is locked to plus any picks already placed.

    Bet.market is derived now (via owner_outcome.market) — there is no single
    "market" per Game; both sides may have picked different markets on the
    same event per api-switch/game-match-audit-plan.md §0 (2c).

    Adds:
      - ``locked_market``: when the slot pre-locks a specific market (Golden
        Game). Both sides must pick within this market; popup uses this to
        constrain the choices and route to the locked-pick endpoint.
      - ``is_current_user_owner``: True when the logged-in user is player_1
        of the match (i.e. the slot's "owner" side). Used by the popup to
        decide which pick endpoint to call.
    """
    game = get_object_or_404(
        Game.objects.select_related(
            'event', 'bet', 'bet__locked_market',
            'match', 'match__player_1', 'match__player_2',
            'owner', 'player_2',
        ),
        id=game_id,
    )
    bet = game.bet
    locked_market = bet.locked_market if bet else None

    owner_market = bet.owner_outcome.market if bet and bet.owner_outcome else None
    player_2_market = (
        bet.player_2_outcome.market if bet and bet.player_2_outcome else None
    )

    is_current_user_owner = (
        request.user.is_authenticated
        and game.match.player_1_id == request.user.id
    )

    return JsonResponse(
        {
            "event": EventSerializer(game.event).data if game.event else None,
            "locked_market": (
                MarketSerializer(locked_market).data if locked_market else None
            ),
            "owner_market": MarketSerializer(owner_market).data if owner_market else None,
            "player_2_market": (
                MarketSerializer(player_2_market).data if player_2_market else None
            ),
            "owner_outcome": (
                SelectionSerializer(bet.owner_outcome).data
                if bet and bet.owner_outcome
                else None
            ),
            "player_2_outcome": (
                SelectionSerializer(bet.player_2_outcome).data
                if bet and bet.player_2_outcome
                else None
            ),
            # Lightweight player info so the picker UI can show who took
            # each already-locked selection.
            "owner_username": game.owner.username if game.owner else None,
            "player_2_username": (
                game.player_2.username if game.player_2 else None
            ),
            "is_current_user_owner": is_current_user_owner,
            "is_golden": game.is_golden,
        }
    )
