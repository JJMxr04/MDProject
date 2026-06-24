"""Opponent scouting — tendencies from a user's actual match picks (Phase 9).

Built from MDProject gameplay data — the picks users make in matches — NOT the
aggregator's bet-tracking table (that's the parked external-wager feature and
holds no match picks). A user's pick in a game is the ``Selection`` on the side
they played:

- ``owner_outcome`` when they own the slot (regular slots, duel challenger) or
  are player_1 of an ownerless Golden Game,
- ``player_2_outcome`` when they're player_2 of a Golden Game or a duel.

``scout_user(user)`` returns a tendencies dict, or ``{"reason":
"insufficient_history", ...}`` below ``MIN_PICKS`` settled picks so the card
shows "not enough history yet" rather than garbage percentages.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q

from core.event.models.odds.selection import SelectionType, SettlementStatus
from core.event.odds.humanize import humanize_selection

MIN_PICKS = 5
RECENT_N = 10
TOP_LEAGUES = 5
# Per-market win-rate is suppressed below this many *decided* (won+lost) picks
# — a 1-for-1 "100%" reads as a strong tell when it's just noise. The record
# (W–L) still shows; only the percentage is withheld.
MIN_MARKET_DECIDED = 3
# Only the three markets the upsell sells get their own row; anything else
# still counts toward the overall record but isn't broken out.
_MARKET_LABELS = {"moneyline": "Moneyline", "spread": "Spread", "total": "Total"}
_MARKET_ORDER = {"moneyline": 0, "spread": 1, "total": 2}
# Shorter than evens = backing a favorite (no consensus-line join needed).
FAVORITE_MAX_ODDS = Decimal("2.0")

_DECIDED = (SettlementStatus.WON, SettlementStatus.LOST)
_SETTLED = _DECIDED + (SettlementStatus.PUSH, SettlementStatus.VOID)


def _win_rate(won: int, lost: int):
    decided = won + lost
    return round(won / decided, 3) if decided else None


def _user_pick(game, user_id):
    """The (selection, picked_at) the ``user`` chose in ``game``, or None.

    owner_outcome ≡ the owner-side pick (regular owner / duel challenger /
    Golden player_1); player_2_outcome ≡ the player_2-side pick (Golden /
    duel player_2). A game owned by the opponent yields None for this user.
    """
    bet = getattr(game, "bet", None)
    if bet is None:
        return None
    match = game.match
    if game.owner_id == user_id:
        return (bet.owner_outcome, bet.owner_picked_at)
    if game.owner_id is None:  # Golden Game — sides are player_1 / player_2
        if match.player_1_id == user_id:
            return (bet.owner_outcome, bet.owner_picked_at)
        if match.player_2_id == user_id:
            return (bet.player_2_outcome, bet.player_2_picked_at)
        return None
    if match.match_type == "duel" and match.player_2_id == user_id:
        return (bet.player_2_outcome, bet.player_2_picked_at)
    return None


def scout_user(user) -> dict:
    """Aggregate ``user``'s match picks into a tendencies dict."""
    from core.game.models import Game

    games = (
        Game.objects.filter(Q(match__player_1=user) | Q(match__player_2=user))
        .select_related(
            "match",
            "bet",
            "bet__owner_outcome", "bet__owner_outcome__market__event__league",
            "bet__owner_outcome__market__event__home_team",
            "bet__owner_outcome__market__event__away_team",
            "bet__owner_outcome__market__subject_team",
            "bet__player_2_outcome", "bet__player_2_outcome__market__event__league",
            "bet__player_2_outcome__market__event__home_team",
            "bet__player_2_outcome__market__event__away_team",
            "bet__player_2_outcome__market__subject_team",
        )
    )

    picks = []  # (selection, picked_at)
    for g in games:
        resolved = _user_pick(g, user.id)
        if resolved and resolved[0] is not None:
            picks.append(resolved)

    total = len(picks)
    settled = [(s, t) for (s, t) in picks if s.settlement_status in _SETTLED]
    if len(settled) < MIN_PICKS:
        return {
            "reason": "insufficient_history",
            "total_picks": total,
            "settled_picks": len(settled),
            "min_picks": MIN_PICKS,
        }

    sels = [s for s, _ in picks]
    wins = sum(1 for s, _ in settled if s.settlement_status == SettlementStatus.WON)
    losses = sum(1 for s, _ in settled if s.settlement_status == SettlementStatus.LOST)
    pushes = sum(1 for s, _ in settled if s.settlement_status == SettlementStatus.PUSH)

    return {
        "reason": None,
        "total_picks": total,
        "settled_picks": len(settled),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": _win_rate(wins, losses),
        "side": {
            "home": sum(1 for s in sels if s.type == SelectionType.HOME),
            "away": sum(1 for s in sels if s.type == SelectionType.AWAY),
        },
        "over_under": {
            "over": sum(1 for s in sels if s.type == SelectionType.OVER),
            "under": sum(1 for s in sels if s.type == SelectionType.UNDER),
        },
        "fav_dog": {
            "favorite": sum(1 for s in sels if s.decimal_odds is not None and s.decimal_odds < FAVORITE_MAX_ODDS),
            "underdog": sum(1 for s in sels if s.decimal_odds is not None and s.decimal_odds >= FAVORITE_MAX_ODDS),
        },
        "markets": _markets(settled),
        "leagues": _leagues(settled),
        "recent_form": _recent_form(settled),
    }


def _markets(settled) -> list[dict]:
    agg: dict[str, dict] = {}
    for s, _ in settled:
        cat = (s.market.category or "OTHER").lower()
        if cat not in _MARKET_LABELS:
            continue  # non-core market — still in the overall record, not broken out
        m = agg.setdefault(cat, {"picks": 0, "wins": 0, "losses": 0})
        m["picks"] += 1
        if s.settlement_status == SettlementStatus.WON:
            m["wins"] += 1
        elif s.settlement_status == SettlementStatus.LOST:
            m["losses"] += 1
    rows = [
        {
            "key": cat,
            "market": _MARKET_LABELS[cat],
            "picks": v["picks"],
            "wins": v["wins"],
            "losses": v["losses"],
            # Withheld below the floor — too few decided picks to mean anything.
            "win_rate": (
                _win_rate(v["wins"], v["losses"])
                if v["wins"] + v["losses"] >= MIN_MARKET_DECIDED
                else None
            ),
        }
        for cat, v in agg.items()
    ]
    return sorted(rows, key=lambda r: (_MARKET_ORDER.get(r["key"], 9), -r["picks"]))


def _league_of(selection):
    market = getattr(selection, "market", None)
    event = getattr(market, "event", None) if market else None
    league = getattr(event, "league", None) if event else None
    return getattr(league, "name", None) or getattr(league, "id", None) if league else None


def _leagues(settled) -> list[dict]:
    agg: dict[str, dict] = {}
    for s, _ in settled:
        name = _league_of(s)
        if not name:
            continue
        lg = agg.setdefault(name, {"league": name, "picks": 0, "wins": 0, "losses": 0})
        lg["picks"] += 1
        if s.settlement_status == SettlementStatus.WON:
            lg["wins"] += 1
        elif s.settlement_status == SettlementStatus.LOST:
            lg["losses"] += 1
    return sorted(agg.values(), key=lambda r: r["picks"], reverse=True)[:TOP_LEAGUES]


def _recent_form(settled) -> list[dict]:
    # Newest first by pick time (None-safe — unpicked-at sorts last).
    ordered = sorted(settled, key=lambda st: (st[1] is not None, st[1]), reverse=True)
    return [
        {
            "type": s.type,
            "result": s.settlement_status,
            "label": humanize_selection(s),
        }
        for s, _ in ordered[:RECENT_N]
    ]
