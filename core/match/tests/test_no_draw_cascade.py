"""No-draw cascade tests (``MatchManager._resolve_winner``).

Matches NEVER end in a draw. The deterministic cascade:
  1. Regular-pick points.
  2. Golden Game pick (zero-sum — at most one side hits).
  3. Sum of decimal odds across winning picks (regular + golden).
  4. Golden-total prediction (closest to actual; equidistant → under wins;
     one-sided prediction wins outright).
  5. Dead heat → the accepter (player_2) wins.

Plus the golden pick flow itself (``Game.objects.pick_on_locked_slot``):
the mandatory tiebreaker-total prediction and the zero-sum selection rule.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from procrastinate.contrib.django.models import ProcrastinateJob

from core.event.models.odds.selection import SettlementStatus
from core.game.models import Game, PickError
from core.game.models.bet import Bet
from core.match.models import Match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
    settle_selection,
)

VICTORY_SUBJECT = "Congratulations, You Won the Match!"
LOST_SUBJECT = "Match Result: You Lost"


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


def _give_regular_win(match, winner_user, league, *, odds="2.0"):
    """Settle one slot owned by ``winner_user`` as WON (at ``odds``) with the
    opponent's pick LOST — winner_user gains exactly 1 regular point."""
    game = (
        match.games.filter(owner=winner_user, is_golden=False)
        .filter(event__isnull=True)
        .order_by("slot")
        .first()
    )
    event = make_event(
        league, status_type="finished", is_finalized=True,
        home_score=10, away_score=7,
    )
    market, home_sel, away_sel = make_two_way_market(event)
    home_sel = settle_selection(home_sel, SettlementStatus.WON)
    away_sel = settle_selection(away_sel, SettlementStatus.LOST)
    # Re-price the WON (owner) selection if the test wants specific odds.
    home_sel.decimal_odds = odds
    home_sel.save(update_fields=["decimal_odds"])
    game.event = event
    game.save(update_fields=["event"])
    Bet.objects.set_owner_outcome(game.bet, home_sel)
    Bet.objects.set_player_2_outcome(game.bet, away_sel)
    return game


class NoDrawCascadeTests(TestCase):
    """Each test hand-wires a match, closes the window, and resolves it."""

    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.league = make_league()

    def _make_match_with_golden(self, *, home_score=None, away_score=None,
                                status_type="notstarted", is_finalized=False):
        """Build an accepted match whose golden game sits on a market we
        control both selections of. Returns (match, golden_home, golden_away).
        """
        golden_league = make_league("GOLDEN")
        golden_event = make_event(
            golden_league,
            status_type=status_type,
            is_finalized=is_finalized,
            home_score=home_score,
            away_score=away_score,
        )
        _, g_home, g_away = make_two_way_market(golden_event)
        match = make_match(self.p1, self.p2, golden_selection=g_home)
        return match, g_home, g_away

    def _set_golden_picks(self, match, *, p1_sel=None, p2_sel=None):
        """Golden is ownerless: owner_outcome ≡ p1's pick, player_2_outcome
        ≡ p2's pick."""
        golden = match.games.get(is_golden=True)
        if p1_sel is not None:
            Bet.objects.set_owner_outcome(golden.bet, p1_sel)
        if p2_sel is not None:
            Bet.objects.set_player_2_outcome(golden.bet, p2_sel)
        return golden

    def _close_window_and_resolve(self, match):
        match.end_date = timezone.now() - timedelta(hours=1)
        match.save(update_fields=["end_date"])
        Match.objects.maybe_complete_match(match)
        match.refresh_from_db()
        return match

    # --- Step 1: regular points dominate -------------------------------

    def test_regular_points_win_ignores_golden(self):
        match, g_home, g_away = self._make_match_with_golden()
        _give_regular_win(match, self.p1, self.league)
        # Golden goes to p2 — must NOT matter, p1 leads on regular points.
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.WON)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)

        self._close_window_and_resolve(match)
        self.assertEqual(match.match_state, "completed")
        self.assertEqual(match.winner, self.p1)

    # --- Step 2: golden pick breaks the tie -----------------------------

    def test_tied_points_golden_p1_hit_wins(self):
        match, g_home, g_away = self._make_match_with_golden()
        settle_selection(g_home, SettlementStatus.WON)
        settle_selection(g_away, SettlementStatus.LOST)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p1)

    def test_tied_points_golden_p2_hit_wins(self):
        match, g_home, g_away = self._make_match_with_golden()
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.WON)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p2)

    # --- Step 3: boldness (winning-odds sums) ---------------------------

    def test_tied_points_golden_missed_higher_odds_sum_wins(self):
        match, g_home, g_away = self._make_match_with_golden()
        # Both golden picks missed → step 2 can't separate.
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.LOST)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)
        # One WON regular each (points stay 1–1) at different odds:
        # p1's winning pick was bolder (3.0 vs 1.5) → p1 wins on step 3.
        _give_regular_win(match, self.p1, self.league, odds="3.0")
        _give_regular_win(match, self.p2, self.league, odds="1.5")

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p1)

    # --- Step 4: golden-total predictions -------------------------------

    def test_prediction_closest_to_actual_total_wins(self):
        # Golden event finished 10–7 → actual total 17.
        match, g_home, g_away = self._make_match_with_golden(
            home_score=10, away_score=7,
            status_type="finished", is_finalized=True,
        )
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.LOST)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)
        # No regular wins → points 0–0 and odds sums 0.0–0.0.
        tb = match.tiebreaker
        tb.owner_total = 16      # |16 - 17| = 1
        tb.player_2_total = 10   # |10 - 17| = 7
        tb.save(update_fields=["owner_total", "player_2_total"])

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p1)

    def test_equidistant_predictions_lower_wins(self):
        # Actual total 17; predictions 18 (p1) vs 16 (p2) — equidistant,
        # the under (lower guess) wins → p2.
        match, g_home, g_away = self._make_match_with_golden(
            home_score=10, away_score=7,
            status_type="finished", is_finalized=True,
        )
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.LOST)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)
        tb = match.tiebreaker
        tb.owner_total = 18
        tb.player_2_total = 16
        tb.save(update_fields=["owner_total", "player_2_total"])

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p2)

    def test_only_p2_predicted_p2_wins(self):
        match, g_home, g_away = self._make_match_with_golden(
            home_score=10, away_score=7,
            status_type="finished", is_finalized=True,
        )
        settle_selection(g_home, SettlementStatus.LOST)
        settle_selection(g_away, SettlementStatus.LOST)
        self._set_golden_picks(match, p1_sel=g_home, p2_sel=g_away)
        tb = match.tiebreaker
        tb.owner_total = None
        tb.player_2_total = 20
        tb.save(update_fields=["owner_total", "player_2_total"])

        self._close_window_and_resolve(match)
        self.assertEqual(match.winner, self.p2)

    # --- Step 5: dead heat → accepter wins ------------------------------

    def test_dead_heat_accepter_wins_and_result_emails_sent(self):
        # Nothing anywhere: no picks, no golden, no predictions. Window
        # closes → everything forfeits to 0–0 and the cascade falls all the
        # way through to "accepter wins".
        match, _, _ = self._make_match_with_golden()
        before_ids = set(_email_jobs().values_list("id", flat=True))

        self._close_window_and_resolve(match)

        self.assertEqual(match.match_state, "completed")
        self.assertIsNotNone(match.winner)
        self.assertEqual(match.winner, self.p2)

        jobs = [j for j in _email_jobs() if j.id not in before_ids]
        self.assertEqual(len(jobs), 2)
        subjects_by_recipient = {
            j.args["recipient"]: j.args["subject"] for j in jobs
        }
        self.assertEqual(subjects_by_recipient.get(self.p2.email), VICTORY_SUBJECT)
        self.assertEqual(subjects_by_recipient.get(self.p1.email), LOST_SUBJECT)
        # Tie emails are gone — matches never draw.
        for j in jobs:
            self.assertNotIn("Tie", j.args["subject"])


class PickOnLockedSlotTests(TestCase):
    """Golden pick flow: mandatory total prediction + zero-sum selections."""

    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        golden_league = make_league("GOLDEN")
        # Default factory start_time = now + 2d → pick window is open.
        self.golden_event = make_event(golden_league)
        _, self.g_home, self.g_away = make_two_way_market(self.golden_event)
        self.match = make_match(self.p1, self.p2, golden_selection=self.g_home)
        self.golden = self.match.games.get(is_golden=True)

    def _pick(self, user, selection, **kwargs):
        return Game.objects.pick_on_locked_slot(
            current_user=user,
            game_id=self.golden.id,
            selection_id=selection.id,
            **kwargs,
        )

    def test_missing_tiebreaker_total_rejected(self):
        with self.assertRaisesMessage(PickError, "Predict the final total"):
            self._pick(self.p1, self.g_home)

    def test_none_tiebreaker_total_rejected(self):
        with self.assertRaisesMessage(PickError, "Predict the final total"):
            self._pick(self.p1, self.g_home, tiebreaker_total=None)

    def test_negative_tiebreaker_total_rejected(self):
        with self.assertRaises(PickError):
            self._pick(self.p1, self.g_home, tiebreaker_total=-1)
        self.golden.bet.refresh_from_db()
        self.assertIsNone(self.golden.bet.owner_outcome)

    def test_valid_pick_stores_prediction_per_side(self):
        self._pick(self.p1, self.g_home, tiebreaker_total=42)
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.owner_outcome_id, self.g_home.id)
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 42)
        self.assertIsNone(tb.player_2_total)

        self._pick(self.p2, self.g_away, tiebreaker_total=33)
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.player_2_outcome_id, self.g_away.id)
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 42)
        self.assertEqual(tb.player_2_total, 33)

    def test_opponents_selection_rejected_zero_sum(self):
        self._pick(self.p1, self.g_home, tiebreaker_total=40)
        with self.assertRaisesMessage(PickError, "opponent already took that side"):
            self._pick(self.p2, self.g_home, tiebreaker_total=35)
        self.golden.bet.refresh_from_db()
        self.assertIsNone(self.golden.bet.player_2_outcome)

    def test_repicking_own_selection_allowed(self):
        self._pick(self.p1, self.g_home, tiebreaker_total=40)
        # Same side again — allowed; the new prediction sticks.
        self._pick(self.p1, self.g_home, tiebreaker_total=44)
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.owner_outcome_id, self.g_home.id)
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 44)

    def test_opponent_picking_other_selection_succeeds(self):
        self._pick(self.p1, self.g_home, tiebreaker_total=40)
        self._pick(self.p2, self.g_away, tiebreaker_total=21)
        self.golden.bet.refresh_from_db()
        self.assertEqual(self.golden.bet.owner_outcome_id, self.g_home.id)
        self.assertEqual(self.golden.bet.player_2_outcome_id, self.g_away.id)


class MatchDetailGoldenCardTests(TestCase):
    """Carried over from the removed tiebreaker-window module — the golden
    card must still surface which market the system locked."""

    def test_detail_page_shows_golden_locked_market(self):
        p1 = make_user("p1")
        p2 = make_user("p2")
        league = make_league("GOLDEN")
        golden_event = make_event(league)
        _, g_home, _ = make_two_way_market(golden_event)
        match = make_match(p1, p2, golden_selection=g_home)

        self.client.force_login(p1)
        detail_url = reverse("core-portal:portal-my-match-detail", args=[match.id])
        r = self.client.get(detail_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Market: Moneyline")
