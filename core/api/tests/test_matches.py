"""/api/v1/matches/ security + behavior.

Detail/list are participant-scoped (non-participant -> 404), with a per-action
cross-user negative test on retrieve. (The old ``tiebreaker`` submit action
was removed with the no-draw cascade — the golden-total prediction now rides
on the golden pick itself.)
"""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase
from core.match.models import Match


class MatchApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")  # non-participant
        # Build a match row directly to avoid the golden-game catalog seed.
        self.match = Match.objects.create(
            player_1=self.alice, player_2=self.bob, match_state="accepted"
        )
        self.list_url = reverse("api-v1:matches-list")

    def _detail_url(self, match):
        return reverse("api-v1:matches-detail", args=[match.id])

    # --- list/detail scope -----------------------------------------------
    def test_participant_sees_match_in_list(self):
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["id"] for row in data}, {str(self.match.id)})

    def test_non_participant_list_is_empty(self):
        self.client.force_authenticate(self.carol)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual(data, [])

    def test_participant_can_retrieve(self):
        self.client.force_authenticate(self.bob)
        resp = self.client.get(self._detail_url(self.match))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual(data["player_1"]["username"], self.alice.username)
        # Privilege/identity fields are not leaked through the nested player.
        self.assertNotIn("email", data["player_1"])
        self.assertNotIn("is_staff", data["player_1"])

    def test_anonymous_is_401(self):
        resp = self.client.get(self._detail_url(self.match))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_user_retrieve_is_404(self):
        self.assert_denies_cross_user(self._detail_url(self.match), self.carol)

    def test_detail_exposes_format(self):
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self._detail_url(self.match)))
        self.assertEqual(data["format"], "MARATHON")
