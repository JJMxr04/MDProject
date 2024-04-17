import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from core.tournament.models.tournament import Tournament, Round, TournamentManager, RoundManager
from core.user.models import User


class TournamentCreationTestCase(TestCase):
    def test_tournament_creation(self):
        start_date = datetime.now()
        max_accepted_players = 16
        tournament = Tournament.objects.create(name="Test Tournament", start_date=start_date,
                                               max_accepted_players=max_accepted_players)

        # Check if tournament was created successfully
        self.assertIsNotNone(tournament)
        self.assertEqual(tournament.name, "Test Tournament")
        self.assertEqual(tournament.max_accepted_players, max_accepted_players)

        # Check if end date was calculated correctly
        expected_end_date = start_date + timedelta(weeks=1)
        self.assertEqual(tournament.end_date.date(), expected_end_date.date())  # This is where the failure occurs

        # Check if levels were calculated correctly
        self.assertEqual(tournament.levels, 4)  # log2(16) = 4


# class TournamentFunctionalityTestCase(TestCase):
#     def setUp(self):
#         self.user = User.objects.create(email="test@example.com", password="password")
#
#     def test_invite_player(self):
#         tournament = Tournament.objects.create(name="Test Tournament", start_date=datetime.now(),
#                                                max_accepted_players=16)
#         invited = Tournament.objects.invitePlayer(tournament.id, self.user.email)
#
#         # Check if player was invited successfully
#         self.assertTrue(invited)
#         self.assertIn(self.user, tournament.invited_players.all())
#
#     def test_accept_invite(self):
#         tournament = Tournament.objects.create(name="Test Tournament", start_date=datetime.now(),
#                                                max_accepted_players=16)
#         Tournament.objects.invitePlayer(tournament.id, self.user.email)
#
#         # Accept invite
#         accepted = Tournament.objects.acceptInvite(tournament.id, self.user.email)
#
#         # Check if invite was accepted successfully
#         self.assertTrue(accepted)
#         self.assertIn(self.user, tournament.players.all())
#
#
# class RoundCreationTestCase(TestCase):
#     def setUp(self):
#         self.tournament = Tournament.objects.create(name="Test Tournament", start_date=datetime.now(),
#                                                     max_accepted_players=16)
#
#     def test_round_creation(self):
#         Tournament.objects.create_rounds(self.tournament)
#
#         # Check if rounds were created
#         self.assertEqual(self.tournament.rounds.count(), 4)  # Four levels for 16 players
#
#     def test_round_linkage(self):
#         Tournament.objects.create_rounds(self.tournament)
#
#         # Check if round linkage is correct
#         for round_obj in self.tournament.rounds.all():
#             if round_obj.level_num > 0:
#                 self.assertIsNotNone(round_obj.prev_round_1)
#
#                 if round_obj.level_num > 1:
#                     self.assertIsNotNone(round_obj.prev_round_2)
