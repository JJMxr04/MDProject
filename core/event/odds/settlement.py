"""Selection settlement — decides which selections won, lost, pushed, or voided.

Two paths:
  - PROVIDER: SGO's per-odd ``score`` field, applied during odds ingest via
    ``core.event.odds.sgo_settlement.grade_event``.
  - COMPUTED: derived from ``Event.home_score`` / ``away_score`` / ``winner_code``
    for the five categories we can reason about without extra data. Runs on
    the event-finished hook and the nightly backfill cron.

Priority: MANUAL > PROVIDER > COMPUTED > PENDING. Never downgrade a row
whose source is already higher-priority.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from core.event.models import Event, Market, Selection

logger = logging.getLogger(__name__)


SOURCE_PRIORITY = {"MANUAL": 3, "PROVIDER": 2, "COMPUTED": 1, "": 0}


# ---------------------------------------------------------------------------
# Per-category settlement functions — mutate sel.settlement_status in place.
# ---------------------------------------------------------------------------


def _settle_moneyline(event: Event, market: Market, selections: Iterable[Selection]):
    winner_by_type = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    winning_type = winner_by_type.get(event.winner_code)
    # NHL regulation-only ML needs regulation score, not final. We don't have
    # that signal; leave pending for the provider flag to resolve.
    if market.type == "NHL_MATCH_WINNER_REG":
        return
    if winning_type is None:
        return
    for sel in selections:
        if sel.type == winning_type:
            sel.settlement_status = "WON"
        elif sel.type in ("HOME", "AWAY", "DRAW"):
            sel.settlement_status = "LOST"


def _settle_total(event: Event, market: Market, selections: Iterable[Selection]):
    if event.home_score is None or event.away_score is None or market.line is None:
        return
    total = event.home_score + event.away_score
    line = float(market.line)
    for sel in selections:
        if sel.type == "OVER":
            sel.settlement_status = "WON" if total > line else "LOST" if total < line else "PUSH"
        elif sel.type == "UNDER":
            sel.settlement_status = "WON" if total < line else "LOST" if total > line else "PUSH"


def _settle_spread(event: Event, market: Market, selections: Iterable[Selection]):
    if event.home_score is None or event.away_score is None or market.line is None:
        return
    margin = event.home_score - event.away_score           # home perspective
    adjusted = margin + float(market.line)                 # line stored home-side
    for sel in selections:
        if sel.type == "HOME":
            sel.settlement_status = "WON" if adjusted > 0 else "LOST" if adjusted < 0 else "PUSH"
        elif sel.type == "AWAY":
            sel.settlement_status = "WON" if adjusted < 0 else "LOST" if adjusted > 0 else "PUSH"


def _settle_props_game(event: Event, market: Market, selections: Iterable[Selection]):
    t = market.type

    if t in ("SOCCER_BTTS", "NHL_BTTS"):
        if event.home_score is None or event.away_score is None:
            return
        both_scored = event.home_score > 0 and event.away_score > 0
        for sel in selections:
            if sel.type == "YES":
                sel.settlement_status = "WON" if both_scored else "LOST"
            elif sel.type == "NO":
                sel.settlement_status = "LOST" if both_scored else "WON"
        return

    if t == "SOCCER_DOUBLE_CHANCE":
        wc = event.winner_code
        if wc is None:
            return
        win_set = {
            "1X": {1, 3},
            "X2": {2, 3},
            "12": {1, 2},
        }
        for sel in selections:
            bucket = win_set.get(sel.type)
            if bucket is None:
                continue
            sel.settlement_status = "WON" if wc in bucket else "LOST"
        return

    if t == "SOCCER_DRAW_NO_BET":
        wc = event.winner_code
        if wc is None:
            return
        if wc == 3:
            for sel in selections:
                if sel.type in ("HOME", "AWAY"):
                    sel.settlement_status = "PUSH"
            return
        winning_type = "HOME" if wc == 1 else "AWAY"
        for sel in selections:
            if sel.type == winning_type:
                sel.settlement_status = "WON"
            elif sel.type in ("HOME", "AWAY"):
                sel.settlement_status = "LOST"
        return

    # First-scorer, corners, cards, overtime yes/no, empty-net goal, exact
    # score — need data we don't store. Leave pending; rely on provider flag.
    return


def _settle_props_team(event: Event, market: Market, selections: Iterable[Selection]):
    t = market.type
    if t in ("SOCCER_TEAM_TOTAL_GOALS", "NHL_TEAM_TOTAL_GOALS"):
        if market.line is None:
            return
        side = market.side
        score = event.home_score if side == "HOME" else event.away_score if side == "AWAY" else None
        if score is None:
            return
        line = float(market.line)
        for sel in selections:
            if sel.type == "OVER":
                sel.settlement_status = "WON" if score > line else "LOST" if score < line else "PUSH"
            elif sel.type == "UNDER":
                sel.settlement_status = "WON" if score < line else "LOST" if score > line else "PUSH"
        return
    # Power-play goals, penalty minutes etc. need split stats we don't store.
    return


SETTLEMENT_FUNCS = {
    "MONEYLINE": _settle_moneyline,
    "TOTAL": _settle_total,
    "SPREAD": _settle_spread,
    "PROPS_GAME": _settle_props_game,
    "PROPS_TEAM": _settle_props_team,
}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


@transaction.atomic
def settle_event(event: Event) -> int:
    """Run computed settlement on every PENDING selection for an event.

    Only touches rows whose current source is '' (untouched) or 'COMPUTED'.
    Returns number of selections updated.

    After bulk-updating, walks affected ``Match`` rows and runs
    ``maybe_complete_match`` — ``bulk_update`` skips ``post_save`` signals so
    the standard Selection-settled signal never fires here.
    """
    if event.status_type != "finished":
        return 0

    now = timezone.now()
    total_updated = 0

    markets = Market.objects.filter(event=event).prefetch_related("selections")
    for market in markets:
        fn = SETTLEMENT_FUNCS.get(market.category)
        if fn is None:
            continue

        touchable = [
            s for s in market.selections.all()
            if SOURCE_PRIORITY.get(s.settlement_source, 0) <= SOURCE_PRIORITY["COMPUTED"]
            and s.settlement_status == "PENDING"
        ]
        if not touchable:
            continue

        original_status = {s.id: s.settlement_status for s in touchable}
        fn(event, market, touchable)

        changed = []
        for sel in touchable:
            if sel.settlement_status != original_status[sel.id]:
                sel.settled_at = now
                sel.settlement_source = "COMPUTED"
                changed.append(sel)

        if changed:
            Selection.objects.bulk_update(
                changed, ["settlement_status", "settled_at", "settlement_source"]
            )
            total_updated += len(changed)

    if total_updated:
        logger.info("Settled %d selections for event %s", total_updated, event.id)
        propagate_to_matches(event)
    return total_updated


def propagate_to_matches(event: Event) -> int:
    """Walk every Match holding a Bet on this event's Selections and run
    ``Match.objects.maybe_complete_match``. Used after bulk-updates that skip
    the standard Selection post_save signal.

    Returns the count of matches inspected (not necessarily completed).
    """
    from django.db.models import Q

    from core.game.models import Bet

    bets = (
        Bet.objects.filter(
            Q(owner_outcome__market__event=event)
            | Q(player_2_outcome__market__event=event)
        )
        .select_related("game", "game__match")
    )
    seen = set()
    matches = []
    for bet in bets:
        game = getattr(bet, "game", None)
        if game is None or game.match_id is None or game.match_id in seen:
            continue
        seen.add(game.match_id)
        matches.append(game.match)

    if not matches:
        return 0

    from core.match.models import Match  # local: dodge circular

    for match in matches:
        Match.objects.maybe_complete_match(match)

    # Peak notification (plan Phase 7 #2) — the bulk paths (computed
    # settlement, provider grading, finalize webhooks) skip post_save, so
    # the golden-hit hook must live here too. Idempotent via the Bet-row
    # claim; runs after completion so finished matches are excluded.
    from core.game.notifications import notify_golden_hits

    notify_golden_hits(event=event)
    return len(matches)


def settle_pending_events(lookback_hours: int = 48) -> dict:
    """Backfill cron entry point. Finds finished events with pending
    selections and runs computed settlement against each."""
    since = timezone.now() - timedelta(hours=lookback_hours)
    events = (
        Event.objects.filter(
            status_type="finished",
            updated__gte=since,
            markets__selections__settlement_status="PENDING",
        )
        .distinct()
    )
    settled = 0
    processed = 0
    for event in events.iterator():
        processed += 1
        settled += settle_event(event)

    void_cutoff = timezone.now() - timedelta(days=7)
    stale_pending = Selection.objects.filter(
        settlement_status="PENDING",
        market__event__start_time__lt=void_cutoff,
        market__event__status_type__in=["postponed", "canceled"],
    )
    voided = stale_pending.update(
        settlement_status="VOID",
        settled_at=timezone.now(),
        settlement_source="COMPUTED",
    )
    if voided:
        logger.info("Voided %d stale pending selections", voided)

    return {"events_processed": processed, "selections_settled": settled, "voided": voided}
