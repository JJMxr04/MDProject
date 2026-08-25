"""Match scoring — pure functions over Selection.settlement_status.

Score for a Match is fully derived. There are no cached `*_score` /
`*_completed` fields anywhere in the data model. Reads always recompute via
`score_match(match)`. This eliminates the desync class that the old denorm
booleans were prone to.

Constants are exposed as module-level for one-line tuning. None of them
are admin-editable; flipping a value here is a code change + redeploy.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Optional, Tuple

from django.utils import timezone

if TYPE_CHECKING:
    from core.event.models import Selection
    from core.game.models import Game
    from core.match.models import Match


REGULAR_POINTS = 1

PUSH_POINTS = 0
VOID_POINTS = 0
UNPICKED_SLOT_PENALTY = 0

DEADLINE_BUFFER = timedelta(hours=8)


def points_for_selection(
    selection: Optional["Selection"],
    *,
    slot_locked: bool,
) -> Optional[int]:
    """Score one side of one game.

    Returns:
      int   — final, scoreable result (0 included).
      None  — still pending; caller treats this as "not yet decided".

    ``slot_locked`` is True when the player can no longer change/add a pick
    on this slot — either because the match end-date has passed OR because
    the event has reached a terminal state. An unpicked side on a locked
    slot is treated as a permanent zero (forfeit).
    """
    base = REGULAR_POINTS

    if selection is None:
        return UNPICKED_SLOT_PENALTY if slot_locked else None

    status = selection.settlement_status
    if status == "WON":
        return base
    if status == "LOST":
        return 0
    if status == "PUSH":
        return PUSH_POINTS
    if status == "VOID":
        return VOID_POINTS
    return None


# Event statuses that lock a slot — picks can no longer change after this.
_TERMINAL_EVENT_STATUSES = ("finished", "postponed", "canceled")


def score_match(match: "Match") -> Tuple[int, int, bool]:
    """Compute (player_1_score, player_2_score, fully_decided) for a Match.

    Regular picks score the match; the Golden Game contributes NO points —
    it is the explicit tiebreaker (see ``golden_winner_side``).

    A slot is "locked" when the match end-date has passed OR the slot's
    event has reached a terminal state — at that point no further picks
    are accepted on that slot, and unpicked sides count as forfeit-zero.

    `fully_decided` is True when every regular (game, side) tuple resolved
    to an int AND — only when the regular score is tied, since that's the
    only case where the golden outcome matters — the Golden Game's sides
    have resolved too. Returning True triggers ``maybe_complete_match``.
    """
    closed = bool(match.end_date and match.end_date <= timezone.now())
    p1_total = 0
    p2_total = 0
    regulars_decided = True
    golden_decided = True

    games = match.games.select_related(
        "bet",
        "bet__owner_outcome",
        "bet__player_2_outcome",
        "owner",
        "player_2",
        "event",
    )
    for game in games:
        # Per-slot lock: terminal event OR overall match-window close.
        event_terminal = bool(
            game.event and game.event.status_type in _TERMINAL_EVENT_STATUSES
        )
        slot_locked = closed or event_terminal
        for side, selection in (
            ("owner", game.bet.owner_outcome),
            ("player_2", game.bet.player_2_outcome),
        ):
            pts = points_for_selection(selection, slot_locked=slot_locked)
            if game.is_golden:
                if pts is None:
                    golden_decided = False
                continue
            if pts is None:
                regulars_decided = False
                continue
            if side == "owner":
                user = game.owner or match.player_1
            else:
                user = game.player_2 or match.player_2
            if user_id_eq(user, match.player_1):
                p1_total += pts
            elif user_id_eq(user, match.player_2):
                p2_total += pts

    tied = p1_total == p2_total
    decided = regulars_decided and (not tied or golden_decided)
    return p1_total, p2_total, decided


def winning_odds_totals(match: "Match") -> Tuple[float, float]:
    """Tie-cascade step 3: each side's sum of decimal odds across WON picks
    (regular + golden). Bolder correct picks beat safe ones — fully derived
    from settlement data, no extra input. Returns (p1_sum, p2_sum) as
    floats (Decimal sums converted; comparison-only, never stored).
    """
    p1_sum = 0.0
    p2_sum = 0.0
    games = match.games.select_related(
        "bet", "bet__owner_outcome", "bet__player_2_outcome",
        "owner", "player_2",
    )
    for game in games:
        for side, selection in (
            ("owner", game.bet.owner_outcome),
            ("player_2", game.bet.player_2_outcome),
        ):
            if selection is None or selection.settlement_status != "WON":
                continue
            odds = float(selection.decimal_odds or 0)
            if side == "owner":
                user = game.owner or match.player_1
            else:
                user = game.player_2 or match.player_2
            if user_id_eq(user, match.player_1):
                p1_sum += odds
            elif user_id_eq(user, match.player_2):
                p2_sum += odds
    return p1_sum, p2_sum


def golden_winner_side(match: "Match") -> Optional[int]:
    """Tie-cascade step 2: resolve from the Golden Game's picks.

    Returns 1 (player_1 wins), 2 (player_2 wins), or None when the golden
    can't separate them — both missed, push/void, or unpicked sides — and
    the cascade continues (matches never end in a draw). With the zero-sum
    golden rule (opponents must take different selections) at most one side
    can hit, so this step decides nearly every tie.

    The Golden Game is ownerless: owner_outcome ≡ player_1's pick,
    player_2_outcome ≡ player_2's pick.
    """
    golden = match.games.select_related(
        "bet", "bet__owner_outcome", "bet__player_2_outcome",
    ).filter(is_golden=True).first()
    if golden is None or golden.bet is None:
        return None

    def hit(selection):
        return selection is not None and selection.settlement_status == "WON"

    p1_hit = hit(golden.bet.owner_outcome)
    p2_hit = hit(golden.bet.player_2_outcome)
    if p1_hit and not p2_hit:
        return 1
    if p2_hit and not p1_hit:
        return 2
    return None


def user_id_eq(a, b) -> bool:
    """Compare users by id without forcing a DB hit on either side."""
    if a is None or b is None:
        return False
    return getattr(a, "id", a) == getattr(b, "id", b)
