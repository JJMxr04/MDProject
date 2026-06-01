"""Phase 3: /api/v1/tournaments/ security + behavior (S-16).

List/detail and the nested rounds action are participant-scoped
(non-participant -> 404). Each endpoint ships a cross-user denial, a list-scope
test, and an anon-401 test.
"""

from __future__ import annotations

from datetime import datetime

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase
from core.tournament.models.tournament import Player, Round, Tournament


class TournamentApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")  # non-participant

        self.t_alice = Tournament.objects.create(
            name="Alice Cup",
            start_date=datetime(2026, 7, 1, 12, 0),
            max_accepted_players=4,
        )
        self.t_bob = Tournament.objects.create(
            name="Bob Cup",
            start_date=datetime(2026, 8, 1, 12, 0),
            max_accepted_players=4,
        )
        self.p_alice = Player.objects.create_player(self.t_alice, self.alice)
        self.p_bob = Player.objects.create_player(self.t_bob, self.bob)

        self.round = Round.objects.create(
            tournament=self.t_alice, level_num=0, player_1=self.p_alice
        )

        self.list_url = reverse("api-v1:tournaments-list")

    def _detail_url(self, tournament):
        return reverse("api-v1:tournaments-detail", args=[tournament.id])

    def _rounds_url(self, tournament):
        return reverse("api-v1:tournaments-rounds", args=[tournament.id])

    # --- list scope -------------------------------------------------------
    def test_participant_sees_own_tournament_in_list(self):
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["id"] for row in data}, {str(self.t_alice.id)})

    def test_list_excludes_other_users_tournaments(self):
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        ids = {row["id"] for row in data}
        self.assertNotIn(str(self.t_bob.id), ids)

    def test_non_participant_list_is_empty(self):
        self.client.force_authenticate(self.carol)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual(data, [])

    def test_anonymous_list_is_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- detail scope -----------------------------------------------------
    def test_participant_can_retrieve(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self._detail_url(self.t_alice))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual(data["name"], "Alice Cup")
        self.assertEqual(data["players"][0]["player"]["username"], self.alice.username)
        # Privilege/identity fields are not leaked through the nested player.
        self.assertNotIn("email", data["players"][0]["player"])
        self.assertNotIn("is_staff", data["players"][0]["player"])

    def test_anonymous_detail_is_401(self):
        resp = self.client.get(self._detail_url(self.t_alice))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_user_retrieve_is_404(self):
        self.assert_denies_cross_user(self._detail_url(self.t_alice), self.carol)

    def test_cross_user_retrieve_other_participant_is_404(self):
        # Bob is a real participant of his own tournament, but not Alice's.
        self.assert_denies_cross_user(self._detail_url(self.t_alice), self.bob)

    # --- rounds action ----------------------------------------------------
    def test_participant_can_list_rounds(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self._rounds_url(self.t_alice))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual({row["id"] for row in data}, {str(self.round.id)})

    def test_anonymous_rounds_is_401(self):
        resp = self.client.get(self._rounds_url(self.t_alice))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_user_rounds_is_404(self):
        self.assert_denies_cross_user(self._rounds_url(self.t_alice), self.carol)

    def test_cross_user_rounds_other_participant_is_404(self):
        self.assert_denies_cross_user(self._rounds_url(self.t_alice), self.bob)
