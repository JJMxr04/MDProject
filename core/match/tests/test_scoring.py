"""Pure ``score_match`` tests over hand-crafted Selection states.

We don't need the full match seed for most of these — we build a Match with
``accept=True``, then directly mutate its 11 games' ``bet.owner_outcome`` /
``bet.player_2_outcome`` to whatever Selection state the test wants and call
``score_match``.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.event.models.odds.selection import SettlementSource, SettlementStatus
from core.game.models.bet import Bet
from core.match.scoring import (
    GOLDEN_POINTS,
    REGULAR_POINTS,
    score_match,
)
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
    settle_selection,
)


def _attach_event_with_market(game, league, *, home_status, away_status):
    """Wire one event with a settled HOME/AWAY market onto a Game's bet."""
    event = make_event(
        league, status_type="finished", is_finalized=True,
        home_score=10, away_score=7,
    )
    _, home_sel, away_sel = make_two_way_market(
        event, home_status=home_status, away_status=away_status,
    )
    game.event = event
    game.save(update_fields=["event"])
    Bet.objects.set_owner_outcome(game.bet, home_sel)
    Bet.objects.set_player_2_outcome(game.bet, away_sel)
    return event, home_sel, away_sel


class ScoreMatchTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.league = make_league()

    def test_all_pending_returns_decided_false(self):
        # Brand-new match; no picks. Every slot is PENDING.
        p1_score, p2_score, decided = score_match(self.match)
        self.assertEqual(p1_score, 0)
        self.assertEqual(p2_score, 0)
        self.assertFalse(decided)

    def test_owner_won_regular_game(self):
        # Pick the first p1-owned regular slot, owner picks HOME (won), opp AWAY (lost).
        game = self.match.games.filter(owner=self.p1, is_golden=False).order_by("slot").first()
        _attach_event_with_market(
            game, self.league,
            home_status=SettlementStatus.WON, away_status=SettlementStatus.LOST,
        )
        # All other 10 slots remain PENDING — match is not yet decided.
        p1, p2, decided = score_match(self.match)
        self.assertEqual(p1, REGULAR_POINTS)  # owner=p1 won → +1 to p1
        self.assertEqual(p2, 0)               # opp=p2 lost → 0
        self.assertFalse(decided)

    def test_golden_game_doubles_points(self):
        golden = self.match.games.get(is_golden=True)
        # On golden, the owner is p1 (set by accept_match). Player_2 is p2.
        _attach_event_with_market(
            golden, self.league,
            home_status=SettlementStatus.WON, away_status=SettlementStatus.LOST,
        )
        p1, p2, decided = score_match(self.match)
        self.assertEqual(p1, GOLDEN_POINTS)
        self.assertEqual(p2, 0)
        self.assertFalse(decided)

    def test_push_and_void_score_zero(self):
        for status in (SettlementStatus.PUSH, SettlementStatus.VOID):
            with self.subTest(status=status):
                fresh_p1 = make_user("p1_" + status[:3].lower())
                fresh_p2 = make_user("p2_" + status[:3].lower())
                m = make_match(fresh_p1, fresh_p2)
                game = m.games.filter(owner=fresh_p1, is_golden=False).order_by("slot").first()
                _attach_event_with_market(
                    game, self.league, home_status=status, away_status=status,
                )
                p1, p2, _ = score_match(m)
                self.assertEqual(p1, 0)
                self.assertEqual(p2, 0)

    def test_unpicked_slot_open_window_returns_pending(self):
        # No picks anywhere; window still open.
        self.match.end_date = timezone.now() + timedelta(days=2)
        self.match.save(update_fields=["end_date"])
        _, _, decided = score_match(self.match)
        self.assertFalse(decided)

    def test_unpicked_slot_closed_window_scores_zero_and_decided_true(self):
        # Window closed → unpicked slots resolve to 0 and the match is decided.
        self.match.end_date = timezone.now() - timedelta(seconds=1)
        self.match.save(update_fields=["end_date"])
        p1, p2, decided = score_match(self.match)
        self.assertEqual(p1, 0)
        self.assertEqual(p2, 0)
        self.assertTrue(decided)

    def test_full_5_5_1_match_total(self):
        """Wire all 11 slots with concrete WON/LOST outcomes and check the
        exact final score. Owner picks HOME (we control whether HOME WON or
        LOST per slot). Opponent picks AWAY (the inverse)."""
        regulars = list(self.match.games.filter(is_golden=False).order_by("slot", "owner_id"))
        golden = self.match.games.get(is_golden=True)

        # Plan: slots 1-3 owner wins, 4-5 opponent wins (each player has 5 slots).
        # That gives:
        #   p1's slots (5 games where p1 is owner):
        #     slots 1-3 → owner=p1 WON → +1 to p1 each = +3 to p1
        #     slots 4-5 → owner=p1 LOST, opponent=p2 WON → +1 to p2 each = +2 to p2
        #   p2's slots (5 games where p2 is owner):
        #     slots 1-3 → owner=p2 WON → +1 to p2 each = +3 to p2
        #     slots 4-5 → owner=p2 LOST, opponent=p1 WON → +1 to p1 each = +2 to p1
        # Subtotal regulars: p1 = 3 + 2 = 5, p2 = 3 + 2 = 5.
        # Golden: HOME WON, owner=p1 → +2 to p1.
        # Final: p1 = 7, p2 = 5.
        for game in regulars:
            home_won = game.slot in (1, 2, 3)
            _attach_event_with_market(
                game, self.league,
                home_status=SettlementStatus.WON if home_won else SettlementStatus.LOST,
                away_status=SettlementStatus.LOST if home_won else SettlementStatus.WON,
            )
        _attach_event_with_market(
            golden, self.league,
            home_status=SettlementStatus.WON, away_status=SettlementStatus.LOST,
        )

        p1, p2, decided = score_match(self.match)
        self.assertTrue(decided)
        self.assertEqual(p1, 7)
        self.assertEqual(p2, 5)
