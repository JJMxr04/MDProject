"""Pick-notification coalescing.

Filling five slots in one sitting used to fire five "your opponent made a
pick" emails. Picks now schedule one debounced summary per
``(match, picker)``: the first pick queues ``send_pick_summary`` with a
short delay, follow-up picks inside the window are absorbed by the
queueing lock, and the job counts the picker's picks at send time.
"""

from __future__ import annotations

from django.conf import settings
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from core.mail.debounce import defer_debounced


@app.task(
    name="core.game.send_pick_summary",
    queue="default",
    retry=RetryStrategy(max_attempts=3, linear_wait=30),
)
def send_pick_summary(match_id, picker_id, recipient_id):
    from core.game.models import Game
    from core.mail.models import Emails
    from core.user.models import User

    try:
        picker = User.objects.get(pk=picker_id)
        recipient = User.objects.get(pk=recipient_id)
    except User.DoesNotExist:
        return 0

    # Count at send time so every pick made during the debounce window is
    # covered by this one email. Includes the picker's golden-game side —
    # the golden slot is ownerless, its sides map to
    # the match players (owner_outcome ≡ player_1).
    pick_count = Game.objects.filter(
        match_id=match_id, owner=picker, is_golden=False,
        bet__owner_outcome__isnull=False,
    ).count() + Game.objects.filter(
        match_id=match_id, player_2=picker, is_golden=False,
        bet__player_2_outcome__isnull=False,
    ).count()

    from core.match.models import Match
    match = Match.objects.filter(pk=match_id).first()
    if match is not None:
        golden_side = (
            "bet__owner_outcome__isnull"
            if match.player_1_id == picker.pk
            else "bet__player_2_outcome__isnull"
        )
        pick_count += Game.objects.filter(
            match_id=match_id, is_golden=True, **{golden_side: False},
        ).count()

    if pick_count == 0:
        return 0

    Emails.send_pick_summary(recipient, picker.username, pick_count)
    return pick_count


def schedule_pick_summary(*, match, picker, recipient) -> bool:
    """Debounced entry point called from the pick flows. One queued
    summary per (match, picker); the recipient is the other side."""
    if recipient is None:
        return False
    return defer_debounced(
        send_pick_summary,
        lock=f"pick-summary-{match.pk}-{picker.pk}",
        delay_seconds=settings.PICK_EMAIL_DEBOUNCE_SECONDS,
        match_id=str(match.pk),
        picker_id=str(picker.pk),
        recipient_id=str(recipient.pk),
    )
