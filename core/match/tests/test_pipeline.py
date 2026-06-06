"""End-to-end: match → games → events → picks → settle → score → complete.

These walk a full lifecycle to validate the integration of:
  - MatchManager.create_match (slot seeding + tiebreaker)
  - Game.objects.upload_pick (owner & opponent flows)
  - Event.objects.upsert_from_spec → settle_event hook
  - score_match
  - MatchManager.maybe_complete_match → calculate_winner

When any of these tests fail, the more granular tests in
``test_match_setup.py`` / ``test_scoring.py`` / ``test_settlement.py`` /
``test_upload_pick.py`` should pinpoint which layer broke.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.event.odds.settlement import settle_event
from core.event.models.odds.selection import SettlementStatus
from core.game.models import Game
from core.game.models.bet import Bet
from core.match.models import Match
from core.match.scoring import score_match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
)


def _build_event_with_market(league, *, home_score, away_score):
    """Fresh event + market with HOME/AWAY selections, all PENDING."""
    event = make_event(
        league,
        start_time=timezone.now() + timedelta(days=2),
        status_type="notstarted",
    )
    market, home, away = make_two_way_market(event)
    return event, market, home, away


def _finalize_event(event, *, home_score, away_score):
    """Set scores and trigger the same lifecycle hook as ingest does."""
    event.status_type = "finished"
    event.is_finalized = True
    event.completed = True
    event.home_score = home_score
    event.away_score = away_score
    event.winner_code = (
        1 if home_score > away_score else 2 if away_score > home_score else 3
    )
    event.save(update_fields=[
        "status_type", "is_finalized", "completed",
        "home_score", "away_score", "winner_code",
    ])
    settle_event(event)


class FullLifecycleTests(TestCase):
    """A full match where p1 wins more slots than p2 and the match completes."""

    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.league = make_league()
        # Control the golden seed so the test can pick + settle its market.
        self.golden_event = make_event(
            self.league, start_time=timezone.now() + timedelta(days=2),
        )
        _, self.g_home, self.g_away = make_two_way_market(self.golden_event)
        self.match = make_match(self.p1, self.p2, golden_selection=self.g_home)

    def _wire_slot(self, game, *, owner_picks_home, home_won):
        """Build an event + selections for one slot, run picks, finalize.

        owner_picks_home — True means whoever owns this slot picks HOME, opponent picks AWAY.
        home_won — final score result; if True home_score > away_score.
        """
        home_score, away_score = (24, 17) if home_won else (10, 31)
        event, market, home, away = _build_event_with_market(
            self.league, home_score=home_score, away_score=away_score,
        )
        owner = game.owner
        opp = game.player_2

        owner_pick = home if owner_picks_home else away
        opp_pick = away if owner_picks_home else home

        Game.objects.upload_pick(
            current_user=owner, match=self.match,
            event_id=event.id, selection_id=owner_pick.id,
        )
        Game.objects.upload_pick(
            current_user=opp, match=self.match,
            event_id=event.id, selection_id=opp_pick.id,
        )
        _finalize_event(event, home_score=home_score, away_score=away_score)
        return event

    def test_full_lifecycle_player_1_wins(self):
        """Plan:
          - 5 p1-owned slots: p1 picks HOME, all home_won → p1 sweeps +5
          - 5 p2-owned slots: p2 picks HOME, only 2 home_won → p2 +2, p1 +3
          - Golden (ownerless): p1 picks HOME, p2 picks AWAY, home wins
            → +2 GOLDEN to p1
        Final: p1 = 5 + 3 + 2 = 10, p2 = 2.
        """
        p1_slots = list(self.match.games.filter(owner=self.p1, is_golden=False).order_by("slot"))
        p2_slots = list(self.match.games.filter(owner=self.p2, is_golden=False).order_by("slot"))
        golden = self.match.games.get(is_golden=True)

        for game in p1_slots:
            self._wire_slot(game, owner_picks_home=True, home_won=True)
        for i, game in enumerate(p2_slots):
            self._wire_slot(game, owner_picks_home=True, home_won=(i < 2))
        # Golden is ownerless — both sides pick independently within the
        # locked market, then the seeded event finalizes.
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=golden.id, selection_id=self.g_home.id,
        )
        Game.objects.pick_on_locked_slot(
            current_user=self.p2, game_id=golden.id, selection_id=self.g_away.id,
        )
        _finalize_event(self.golden_event, home_score=24, away_score=17)

        p1_score, p2_score, decided = score_match(self.match)
        self.assertTrue(decided, "every slot is settled, match should be fully decided")
        self.assertEqual(p1_score, 10)
        self.assertEqual(p2_score, 2)

        Match.objects.maybe_complete_match(self.match)
        self.match.refresh_from_db()
        self.assertEqual(self.match.match_state, "completed")
        self.assertEqual(self.match.winner, self.p1)


class WindowClosedWithUnpickedSlotsTests(TestCase):
    """Match window expires before all picks made — unpicked slots resolve to 0."""

    def test_match_completes_with_partial_picks(self):
        p1 = make_user("p1")
        p2 = make_user("p2")
        match = make_match(p1, p2)
        league = make_league()

        # Pick exactly one p1 slot and finalize that event in p1's favor.
        slot = match.games.filter(owner=p1, is_golden=False).order_by("slot").first()
        event, _, home, _ = _build_event_with_market(league, home_score=20, away_score=10)
        Game.objects.upload_pick(
            current_user=p1, match=match, event_id=event.id, selection_id=home.id,
        )
        # Opponent never picks. Owner is the only one who scored.
        _finalize_event(event, home_score=20, away_score=10)

        # Close the window.
        match.end_date = timezone.now() - timedelta(seconds=1)
        match.save(update_fields=["end_date"])

        Match.objects.maybe_complete_match(match)
        match.refresh_from_db()
        self.assertEqual(match.match_state, "completed")
        # p1 won exactly one regular slot (1 pt). All other slots had no picks
        # → 0 points each. p1 wins the match.
        self.assertEqual(match.winner, p1)


class VoidedEventReopensSlotTests(TestCase):
    """Settlement-plan §5: cancellation triggers reopen_games_for_voided_event."""

    def test_cancellation_clears_outcome_when_window_open(self):
        from core.event.models import Event
        from core.game.events import reopen_games_for_voided_event

        p1 = make_user("p1")
        p2 = make_user("p2")
        match = make_match(p1, p2)
        league = make_league()

        slot = match.games.filter(owner=p1, is_golden=False).order_by("slot").first()
        event, _, home, away = _build_event_with_market(league, home_score=0, away_score=0)
        Game.objects.upload_pick(
            current_user=p1, match=match, event_id=event.id, selection_id=home.id,
        )
        Game.objects.upload_pick(
            current_user=p2, match=match, event_id=event.id, selection_id=away.id,
        )
        # Sanity: bet is wired up.
        slot.refresh_from_db()
        slot.bet.refresh_from_db()
        self.assertIsNotNone(slot.bet.owner_outcome)
        self.assertIsNotNone(slot.bet.player_2_outcome)

        # Cancel the event. Match window is still open → slot should reopen.
        event.status_type = "canceled"
        event.feed_locked = True
        event.save(update_fields=["status_type", "feed_locked"])
        reopened = reopen_games_for_voided_event(event)
        self.assertEqual(reopened, 1)

        slot.refresh_from_db()
        slot.bet.refresh_from_db()
        self.assertIsNone(slot.event_id)
        self.assertIsNone(slot.bet.owner_outcome)
        self.assertIsNone(slot.bet.player_2_outcome)
