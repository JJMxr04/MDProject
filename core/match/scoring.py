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
from typing import Optional, Tuple, TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from core.event.models import Selection
    from core.game.models import Game
    from core.match.models import Match


REGULAR_POINTS = 1
GOLDEN_POINTS = 2

PUSH_POINTS = 0
VOID_POINTS = 0
UNPICKED_SLOT_PENALTY = 0

DEADLINE_BUFFER = timedelta(hours=8)


def points_for_selection(
    selection: Optional["Selection"],
    *,
    is_golden: bool,
    match_window_closed: bool,
) -> Optional[int]:
    """Score one side of one game.

    Returns:
      int   — final, scoreable result (0 included).
      None  — still pending; caller treats this as "not yet decided".
    """
    base = GOLDEN_POINTS if is_golden else REGULAR_POINTS

    if selection is None:
        return UNPICKED_SLOT_PENALTY if match_window_closed else None

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


def score_match(match: "Match") -> Tuple[int, int, bool]:
    """Compute (player_1_score, player_2_score, fully_decided) for a Match.

    `fully_decided` is True when every (game, side) tuple resolved to an int —
    either via a settled Selection or via the match-window-closed unpicked
    penalty. False means at least one slot is still PENDING with the window
    open.
    """
    closed = bool(match.end_date and match.end_date <= timezone.now())
    p1_total = 0
    p2_total = 0
    decided = True

    games = match.games.select_related(
        "bet",
        "bet__owner_outcome",
        "bet__player_2_outcome",
        "owner",
        "player_2",
    )
    for game in games:
        for side, selection in (
            ("owner", game.bet.owner_outcome),
            ("player_2", game.bet.player_2_outcome),
        ):
            pts = points_for_selection(
                selection,
                is_golden=game.is_golden,
                match_window_closed=closed,
            )
            if pts is None:
                decided = False
                continue
            user = game.owner if side == "owner" else game.player_2
            if user_id_eq(user, match.player_1):
                p1_total += pts
            elif user_id_eq(user, match.player_2):
                p2_total += pts

    return p1_total, p2_total, decided


def user_id_eq(a, b) -> bool:
    """Compare users by id without forcing a DB hit on either side."""
    if a is None or b is None:
        return False
    return getattr(a, "id", a) == getattr(b, "id", b)
