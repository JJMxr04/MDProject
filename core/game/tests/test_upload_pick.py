"""Game.objects.upload_pick — owner & opponent flows + validation rejections."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.event.models import MarketCategory
from core.game.models import Game, PickError
from core.match.tests.factories import (
    make_event,
    make_league,
    make_market,
    make_match,
    make_selection,
    make_two_way_market,
    make_user,
)


class OwnerPickTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.league = make_league()
        # Comfortably-far-out event so the 8h owner deadline is satisfied.
        self.event = make_event(
            self.league,
            start_time=timezone.now() + timedelta(days=2),
        )
        self.market, self.home, self.away = make_two_way_market(self.event)

    def test_owner_pick_happy_path(self):
        Game.objects.upload_pick(
            current_user=self.p1,
            match=self.match,
            event_id=self.event.id,
            selection_id=self.home.id,
        )
        # First empty owner slot for p1 should now have the event + bet.
        slot = self.match.games.filter(owner=self.p1, event=self.event).first()
        self.assertIsNotNone(slot)
        slot.bet.refresh_from_db()
        self.assertEqual(slot.bet.owner_outcome_id, self.home.id)
        self.assertEqual(slot.bet.owner_decimal_odds_at_pick, self.home.decimal_odds)
        self.assertIsNotNone(slot.bet.owner_picked_at)

    def test_owner_pick_too_close_to_start_rejected(self):
        # Move the event to 4h from now — under the 8h owner deadline.
        self.event.start_time = timezone.now() + timedelta(hours=4)
        self.event.save(update_fields=["start_time"])
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=self.p1,
                match=self.match,
                event_id=self.event.id,
                selection_id=self.home.id,
            )
        self.assertIn("8 hours", str(ctx.exception))

    def test_invalid_selection_id_raises(self):
        with self.assertRaises(PickError):
            Game.objects.upload_pick(
                current_user=self.p1,
                match=self.match,
                event_id=self.event.id,
                selection_id="not-a-real-selection-id",
            )

    def test_pick_by_non_participant_rejected(self):
        outsider = make_user("outsider")
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=outsider,
                match=self.match,
                event_id=self.event.id,
                selection_id=self.home.id,
            )
        self.assertIn("Not a participant", str(ctx.exception))

    def test_pick_on_unaccepted_match_rejected(self):
        match = make_match(self.p1, self.p2, accept=False)
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=self.p1,
                match=match,
                event_id=self.event.id,
                selection_id=self.home.id,
            )
        self.assertIn("not active", str(ctx.exception).lower())


class OpponentPickTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.league = make_league()
        self.event = make_event(self.league, start_time=timezone.now() + timedelta(days=2))
        self.market, self.home, self.away = make_two_way_market(self.event)

    def test_opponent_picks_after_owner_same_event(self):
        # Owner picks first.
        Game.objects.upload_pick(
            current_user=self.p1, match=self.match,
            event_id=self.event.id, selection_id=self.home.id,
        )
        # Opponent picks the AWAY side of the same market.
        Game.objects.upload_pick(
            current_user=self.p2, match=self.match,
            event_id=self.event.id, selection_id=self.away.id,
        )
        slot = self.match.games.get(owner=self.p1, event=self.event)
        slot.bet.refresh_from_db()
        self.assertEqual(slot.bet.owner_outcome_id, self.home.id)
        self.assertEqual(slot.bet.player_2_outcome_id, self.away.id)

    def test_opponent_picks_different_market_same_event(self):
        # Owner picks moneyline HOME; opponent picks total OVER on a different market.
        Game.objects.upload_pick(
            current_user=self.p1, match=self.match,
            event_id=self.event.id, selection_id=self.home.id,
        )
        total_market = make_market(self.event, category=MarketCategory.TOTAL, line=44.5)
        over = make_selection(total_market, selection_type="OVER")
        Game.objects.upload_pick(
            current_user=self.p2, match=self.match,
            event_id=self.event.id, selection_id=over.id,
        )
        slot = self.match.games.get(owner=self.p1, event=self.event)
        slot.bet.refresh_from_db()
        self.assertEqual(slot.bet.owner_outcome_id, self.home.id)
        self.assertEqual(slot.bet.player_2_outcome_id, over.id)

    def test_duplicate_event_market_pair_across_slots_rejected(self):
        # Owner-side first pick lands on slot 1.
        Game.objects.upload_pick(
            current_user=self.p1, match=self.match,
            event_id=self.event.id, selection_id=self.home.id,
        )
        # A second p1-owner pick on the same (event, market) must be refused.
        with self.assertRaises(PickError) as ctx:
            Game.objects.upload_pick(
                current_user=self.p1, match=self.match,
                event_id=self.event.id, selection_id=self.away.id,
            )
        self.assertIn("already been picked", str(ctx.exception))
