"""Game-side reactions to Event lifecycle changes.

Kept separate from `core.event.odds.settlement` so the settlement engine
remains free of game/match knowledge.
"""

from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

from core.event.models import Event
from core.game.models import Bet

logger = logging.getLogger(__name__)


def reopen_games_for_voided_event(event: Event) -> int:
    """Null out Bet outcomes pointing at this event when it transitions to
    postponed/canceled, *but only if the holding match's window is still open*.

    Match-window-closed slots are left as-is — the eventual VOID on the
    selection will score 0 via the unpicked-penalty path in scoring.py.

    Returns the number of bets reopened.
    """
    if event.status_type not in ("postponed", "canceled"):
        return 0

    affected = (
        Bet.objects.filter(
            Q(owner_outcome__market__event=event)
            | Q(player_2_outcome__market__event=event)
        )
        .select_related("game", "game__match")
    )

    now = timezone.now()
    reopened = 0
    for bet in affected:
        game = getattr(bet, "game", None)
        if game is None or game.match is None:
            continue
        match = game.match
        if match.end_date and match.end_date <= now:
            continue  # window closed — let the VOID propagate via scoring

        update_fields = []
        if bet.owner_outcome and bet.owner_outcome.market.event_id == event.id:
            bet.owner_outcome = None
            bet.owner_decimal_odds_at_pick = None
            bet.owner_picked_at = None
            update_fields += [
                "owner_outcome",
                "owner_decimal_odds_at_pick",
                "owner_picked_at",
            ]
        if bet.player_2_outcome and bet.player_2_outcome.market.event_id == event.id:
            bet.player_2_outcome = None
            bet.player_2_decimal_odds_at_pick = None
            bet.player_2_picked_at = None
            update_fields += [
                "player_2_outcome",
                "player_2_decimal_odds_at_pick",
                "player_2_picked_at",
            ]
        if update_fields:
            update_fields.append("updated_at")
            bet.save(update_fields=update_fields)

        # Drop the event reference so the slot is fully empty for repick.
        if game.event_id == event.id:
            game.event = None
            game.save(update_fields=["event"])
        reopened += 1

    if reopened:
        logger.info(
            "reopen_games_for_voided_event: reopened %d bets for event=%s status=%s",
            reopened,
            event.id,
            event.status_type,
        )
    return reopened
