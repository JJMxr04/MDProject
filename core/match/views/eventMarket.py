from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from core.event.serializers.event import EventSerializer
from core.event.serializers.market import MarketSerializer
from core.event.serializers.selection import SelectionSerializer
from core.game.models import Game


@require_GET
@login_required(login_url="/auth/login/")
def event_markets(request, game_id):
    """Return the event the slot is locked to plus any picks already placed.

    Bet.market is derived now (via owner_outcome.market) — there is no single
    "market" per Game; both sides may have picked different markets on the
    same event per api-switch/game-match-audit-plan.md §0 (2c).
    """
    game = get_object_or_404(Game, id=game_id)
    bet = game.bet

    owner_market = bet.owner_outcome.market if bet and bet.owner_outcome else None
    player_2_market = (
        bet.player_2_outcome.market if bet and bet.player_2_outcome else None
    )

    return JsonResponse(
        {
            "event": EventSerializer(game.event).data if game.event else None,
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
        }
    )
