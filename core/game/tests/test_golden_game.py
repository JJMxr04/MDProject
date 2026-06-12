"""Golden Game — ownerless slot, symmetric picks, generic-flow isolation.

The Golden Game belongs to the match (owner/player_2 are NULL); both players
pick within its locked market independently via ``pick_on_locked_slot`` —
neither side ever waits on the other. The generic ``upload_pick`` flow must
never route a pick onto the golden slot (that's what used to raise
"Owner has not picked yet on this slot" at player_2).
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.event.models import MarketCategory
from core.game.models import Game, PickError
from core.match.models import TieBreaker
from core.match.scoring import score_match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_market,
    make_match,
    make_selection,
    make_two_way_market,
    make_user,
    settle_selection,
)


class GoldenGameBase(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        # Control the golden seed so tests can reference its market/selections.
        league = make_league("GOLDEN")
        self.golden_event = make_event(
            league, start_time=timezone.now() + timedelta(days=2),
        )
        self.golden_market, self.g_home, self.g_away = make_two_way_market(
            self.golden_event,
        )
        self.match = make_match(self.p1, self.p2, golden_selection=self.g_home)
        self.golden = self.match.games.get(is_golden=True)


class GoldenGameCreationTests(GoldenGameBase):
    def test_golden_game_has_no_owner(self):
        self.assertIsNone(self.golden.owner)
        self.assertIsNone(self.golden.player_2)
        self.assertEqual(self.golden.bet.locked_market_id, self.golden_market.id)
        # No side is pre-picked — the seed selection is only a vehicle.
        self.assertIsNone(self.golden.bet.owner_outcome)
        self.assertIsNone(self.golden.bet.player_2_outcome)


class GoldenGameSymmetricPickTests(GoldenGameBase):
    def test_player_2_can_pick_before_player_1(self):
        # No "owner submits first" gate — player_2 picks on a fresh golden slot.
        Game.objects.pick_on_locked_slot(
            current_user=self.p2,
            game_id=self.golden.id,
            selection_id=self.g_away.id,
            tiebreaker_total=41,
        )
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.player_2_outcome_id, self.g_away.id)
        self.assertIsNone(self.golden.bet.owner_outcome)

    def test_player_1_can_pick_before_player_2(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p1,
            game_id=self.golden.id,
            selection_id=self.g_home.id,
            tiebreaker_total=38,
        )
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.owner_outcome_id, self.g_home.id)
        self.assertIsNone(self.golden.bet.player_2_outcome)

    def test_both_sides_pick_independently(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p2, game_id=self.golden.id,
            selection_id=self.g_away.id, tiebreaker_total=41,
        )
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=38,
        )
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.owner_outcome_id, self.g_home.id)
        self.assertEqual(self.golden.bet.player_2_outcome_id, self.g_away.id)

    def test_pick_stores_total_prediction(self):
        # The prediction (cascade step 4) rides on the golden pick itself.
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=38,
        )
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 38)
        self.assertIsNone(tb.player_2_total)

    def test_selection_outside_locked_market_rejected(self):
        other_market = make_market(
            self.golden_event, category=MarketCategory.TOTAL, line=44.5,
        )
        over = make_selection(other_market, selection_type="OVER")
        with self.assertRaises(PickError) as ctx:
            Game.objects.pick_on_locked_slot(
                current_user=self.p1, game_id=self.golden.id,
                selection_id=over.id, tiebreaker_total=38,
            )
        self.assertIn("locked market", str(ctx.exception))


class GoldenGameGenericFlowIsolationTests(GoldenGameBase):
    """The generic upload_pick flow must never land on the golden slot."""

    def test_player_2_generic_pick_not_blocked_by_owner_gate(self):
        # Before the golden slot was excluded from the opponent lookup this
        # raised "Owner has not picked yet on this slot".
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=self.p2,
                match=self.match,
                event_id=self.golden_event.id,
                selection_id=self.g_away.id,
            )
        self.assertNotIn("Owner has not picked", str(ctx.exception))
        self.assertIn("Golden Game", str(ctx.exception))

    def test_player_1_generic_pick_on_golden_market_redirected(self):
        # Previously player_1 silently claimed a NEW regular slot with the
        # golden event. Now the locked market is reserved.
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=self.p1,
                match=self.match,
                event_id=self.golden_event.id,
                selection_id=self.g_home.id,
            )
        self.assertIn("Golden Game", str(ctx.exception))
        # No regular slot was claimed.
        self.assertFalse(
            self.match.games.filter(
                is_golden=False, event=self.golden_event,
            ).exists()
        )

    def test_other_market_on_golden_event_claims_regular_slot(self):
        # A different market on the same event is fair game for a regular slot.
        total_market = make_market(
            self.golden_event, category=MarketCategory.TOTAL, line=44.5,
        )
        over = make_selection(total_market, selection_type="OVER")
        game = Game.objects.upload_pick(
            current_user=self.p2,
            match=self.match,
            event_id=self.golden_event.id,
            selection_id=over.id,
        )
        self.assertFalse(game.is_golden)
        self.assertEqual(game.owner, self.p2)
        game.bet.refresh_from_db()
        self.assertEqual(game.bet.owner_outcome_id, over.id)


class GoldenGameScoringTests(GoldenGameBase):
    def test_golden_contributes_no_match_points(self):
        # The golden game is the tiebreaker, not a scoring slot — a settled
        # golden win adds nothing to the match score (no-draw cascade).
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=38,
        )
        Game.objects.pick_on_locked_slot(
            current_user=self.p2, game_id=self.golden.id,
            selection_id=self.g_away.id, tiebreaker_total=41,
        )
        settle_selection(self.g_home, "WON")
        settle_selection(self.g_away, "LOST")

        p1_score, p2_score, _ = score_match(self.match)
        self.assertEqual(p1_score, 0)
        self.assertEqual(p2_score, 0)


class GoldenGameZeroSumTests(GoldenGameBase):
    def test_opponent_selection_is_off_the_board(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=38,
        )
        with self.assertRaises(PickError) as ctx:
            Game.objects.pick_on_locked_slot(
                current_user=self.p2, game_id=self.golden.id,
                selection_id=self.g_home.id, tiebreaker_total=40,
            )
        self.assertIn("opponent already took that side", str(ctx.exception))

    def test_own_repick_of_same_selection_allowed(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=38,
        )
        # Re-submitting (e.g. to revise the prediction) is fine.
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=44,
        )
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 44)

    def test_prediction_required(self):
        with self.assertRaises(PickError) as ctx:
            Game.objects.pick_on_locked_slot(
                current_user=self.p1, game_id=self.golden.id,
                selection_id=self.g_home.id,
            )
        self.assertIn("Predict the final total", str(ctx.exception))

    def test_negative_prediction_rejected(self):
        with self.assertRaises(PickError):
            Game.objects.pick_on_locked_slot(
                current_user=self.p1, game_id=self.golden.id,
                selection_id=self.g_home.id, tiebreaker_total=-3,
            )


class TieBreakerSideTests(GoldenGameBase):
    def test_set_player_2_total_writes_player_2_total(self):
        tb = self.match.tiebreaker
        TieBreaker.objects.set_owner_total(tiebreaker=tb, total=40)
        TieBreaker.objects.set_player_2_total(tiebreaker=tb, total=50)
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 40)
        self.assertEqual(tb.player_2_total, 50)

    def test_calculate_event_total_caches_combined_score(self):
        tb = self.match.tiebreaker
        event = self.golden_event
        event.home_score, event.away_score = 24, 20
        event.save(update_fields=["home_score", "away_score"])

        self.assertEqual(TieBreaker.objects.calculate_event_total(tb), 44)
        tb.refresh_from_db()
        self.assertEqual(tb.total, 44)
