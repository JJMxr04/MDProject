"""Peak notification #2: "your golden pick hit".

One shared helper called from BOTH settlement paths — the per-selection
``post_save`` signal (``core/game/signals.py``) and the bulk
``propagate_to_matches`` walk (``core/event/odds/settlement.py``), which
skips signals via ``bulk_update``/queryset ``update``.

Exactly-once: the notification is claimed by an atomic UPDATE on
``Bet.golden_hit_notified_at`` (NULL → now). Re-settles, re-saves, and
webhook replays lose the claim race and send nothing. Matches that are
already completed are skipped — the result email owns that moment.
"""

from __future__ import annotations

import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def notify_golden_hits(*, event=None, selection=None) -> int:
    """Notify the winner side of any golden game whose pick just settled
    WON. Scope by ``event`` (bulk path) or a single ``selection`` (signal
    path). Returns the number of notifications sent."""
    from core.game.models import Game

    games = Game.objects.filter(is_golden=True).select_related(
        "bet", "bet__owner_outcome", "bet__player_2_outcome",
        "match", "match__player_1", "match__player_2",
    )
    if selection is not None:
        games = games.filter(
            Q(bet__owner_outcome=selection) | Q(bet__player_2_outcome=selection)
        )
    elif event is not None:
        games = games.filter(event=event)
    else:
        return 0

    sent = 0
    for game in games:
        if _notify_one(game):
            sent += 1
    return sent


def _notify_one(game) -> bool:
    from core.game.models import Bet
    from core.mail.models import Emails
    from core.match.scoring import score_match

    match = game.match
    bet = game.bet
    if bet is None or match is None or match.player_2 is None:
        return False
    # Completed matches get the result email instead — never both.
    if match.match_state == "completed":
        return False

    # Golden sides: owner_outcome ≡ player_1, player_2_outcome ≡ player_2.
    # At most one side can be WON (zero-sum picks, one winner per market).
    if bet.owner_outcome is not None and bet.owner_outcome.settlement_status == "WON":
        winner, opponent = match.player_1, match.player_2
    elif (
        bet.player_2_outcome is not None
        and bet.player_2_outcome.settlement_status == "WON"
    ):
        winner, opponent = match.player_2, match.player_1
    else:
        return False

    # Atomic claim — the exactly-once guard across every settlement path.
    claimed = Bet.objects.filter(
        pk=bet.pk, golden_hit_notified_at__isnull=True,
    ).update(golden_hit_notified_at=timezone.now())
    if not claimed:
        return False

    p1_score, p2_score, _ = score_match(match)
    your_score, their_score = (
        (p1_score, p2_score) if winner == match.player_1 else (p2_score, p1_score)
    )
    try:
        Emails.send_golden_hit(
            winner, opponent.username, your_score, their_score, match_id=match.id,
        )
    except Exception:  # noqa: BLE001 — a mail hiccup must not poison settlement
        logger.exception("golden-hit notification failed for match=%s", match.id)
    return True
