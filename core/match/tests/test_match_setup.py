"""Match creation + 5+5+1 game seeding."""

from django.test import TestCase

from core.match.tests.factories import make_user


class MatchSetupTests(TestCase):
    def test_accept_match_seeds_5_owner_5_opp_1_golden(self):
        from core.match.models import Match

        p1 = make_user("p1")
        p2 = make_user("p2")
        match = Match.objects.create_match(player_1=p1, player_2=p2)

        self.assertEqual(match.match_state, "accepted")
        self.assertEqual(match.player_1, p1)
        self.assertEqual(match.player_2, p2)

        regulars = match.games.filter(is_golden=False)
        goldens = match.games.filter(is_golden=True)

        self.assertEqual(regulars.count(), 10)
        self.assertEqual(goldens.count(), 1)

        # 5 slots owned by each player
        self.assertEqual(regulars.filter(owner=p1).count(), 5)
        self.assertEqual(regulars.filter(owner=p2).count(), 5)

        # Slots are 1..5, opponent on each is the other player
        for slot in range(1, 6):
            p1_game = regulars.get(owner=p1, slot=slot)
            self.assertEqual(p1_game.player_2, p2)
            p2_game = regulars.get(owner=p2, slot=slot)
            self.assertEqual(p2_game.player_2, p1)

        # All slots seeded with an empty Bet row, no event yet (golden gets
        # auto-seeded with an event when a candidate exists; in this test no
        # events have markets so the golden has no event either).
        for game in regulars:
            self.assertIsNone(game.event)
            self.assertIsNotNone(game.bet)
            self.assertIsNone(game.bet.owner_outcome)
            self.assertIsNone(game.bet.player_2_outcome)

    def test_tiebreaker_row_created(self):
        from core.match.models import Match

        p1 = make_user("p1")
        p2 = make_user("p2")
        match = Match.objects.create_match(player_1=p1, player_2=p2)

        self.assertIsNotNone(match.tiebreaker)
        # Tiebreaker points at the golden game.
        golden = match.games.get(is_golden=True)
        self.assertEqual(match.tiebreaker.golden_game, golden)
