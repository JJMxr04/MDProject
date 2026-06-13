from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.event.models import Selection
from core.game.models import Bet


@receiver(post_save, sender=Selection)
def selection_settlement_propagated(sender, instance, **kwargs):
    """When a Selection settles (WON/LOST/PUSH/VOID), check whether any Match
    holding that Selection on either side is now decided and finalize it.

    Triggers on every Selection save. The early-return on PENDING keeps cost
    near-zero for odds refreshes that don't change settlement state.
    """
    if instance.settlement_status == "PENDING":
        return

    bets = (
        Bet.objects.filter(
            Q(owner_outcome=instance) | Q(player_2_outcome=instance)
        )
        .select_related("game", "game__match")
    )

    seen_match_ids = set()
    matches = []
    for bet in bets:
        game = getattr(bet, "game", None)
        if game is None or game.match_id in seen_match_ids:
            continue
        seen_match_ids.add(game.match_id)
        matches.append(game.match)

    if not matches:
        return

    # Imported here to dodge circular import (match -> game -> match).
    from core.match.models import Match

    for match in matches:
        Match.objects.maybe_complete_match(match)

    # Peak notification (plan Phase 7 #2): "your golden pick hit". Runs
    # AFTER completion so a match that just finished gets only its result
    # email. The helper's atomic claim makes re-saves no-ops.
    if instance.settlement_status == "WON":
        from core.game.notifications import notify_golden_hits

        notify_golden_hits(selection=instance)
