"""/api/v1/friends/ security + behavior.

List is scoped to the requester's own M2M; add-by-code and remove are exercised
with the binding cross-user negative test (User B cannot remove User A's edge).
"""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase


class FriendApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.carol = self.make_user("carol")
        # alice <-> bob are friends; carol is a stranger.
        self.alice.add_friend(self.bob)
        self.bob.add_friend(self.alice)
        self.list_url = reverse("api-v1:friends-list")

    def _detail_url(self, user):
        return reverse("api-v1:friends-detail", args=[user.public_id])

    # --- list is scoped --------------------------------------------------
    def test_list_returns_only_own_friends(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual({row["username"] for row in data}, {self.bob.username})

    def test_carol_list_is_empty(self):
        self.client.force_authenticate(self.carol)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual(data, [])

    def test_anonymous_list_is_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")

    # --- add by friend code ----------------------------------------------
    def test_add_friend_by_code(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post(
            self.list_url, {"friend_code": self.carol.friend_code}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.alice.is_friend(self.carol))
        self.assertTrue(self.carol.is_friend(self.alice))

    def test_add_unknown_code_is_400(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post(self.list_url, {"friend_code": "ZZZZZZZZ"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_error_envelope(resp, code="validation_error")

    def test_cannot_add_self(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.post(
            self.list_url, {"friend_code": self.alice.friend_code}, format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- remove -----------------------------------------------------------
    def test_owner_can_remove_friend(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.delete(self._detail_url(self.bob))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.alice.is_friend(self.bob))
        self.assertFalse(self.bob.is_friend(self.alice))

    def test_remove_non_friend_is_404(self):
        # carol is not alice's friend -> 404 (not in scoped queryset).
        self.client.force_authenticate(self.alice)
        resp = self.client.delete(self._detail_url(self.carol))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_user_cannot_remove_others_friend(self):
        # carol tries to remove bob from alice's list (via bob's url) ->
        # 404, because the queryset is carol's own friends, not alice's. The
        # alice<->bob edge must survive.
        self.assert_denies_cross_user(
            self._detail_url(self.bob), self.carol, method="delete"
        )
        self.assertTrue(self.alice.is_friend(self.bob))

    def test_cross_user_cannot_see_via_list(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["username"] for row in data}, {self.alice.username})
