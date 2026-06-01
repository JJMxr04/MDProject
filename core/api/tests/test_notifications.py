"""Phase 1 pilot: /api/v1/notifications/ security + behavior (plan 07/10).

The binding negative test ("User B → 404 for User A's object") plus list-scope
and mark-read behavior.
"""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase
from core.mail.models import Notification


class NotificationApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.a1 = Notification.objects.create_notification(self.alice, "a-one")
        self.a2 = Notification.objects.create_notification(self.alice, "a-two")
        self.b1 = Notification.objects.create_notification(self.bob, "b-one")
        self.list_url = reverse("api-v1:notifications-list")
        self.count_url = reverse("api-v1:notifications-count")

    def _detail_url(self, notif):
        return reverse("api-v1:notifications-detail", args=[notif.id])

    # --- list is scoped ---------------------------------------------------
    def test_list_returns_only_own_notifications(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        messages = {row["message"] for row in data}
        self.assertEqual(messages, {"a-one", "a-two"})

    def test_anonymous_list_is_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")

    def test_count_is_own_count(self):
        self.client.force_authenticate(self.bob)
        resp = self.client.get(self.count_url)
        data = self.assert_success_envelope(resp)
        self.assertEqual(data["count"], 1)

    # --- mark read --------------------------------------------------------
    def test_owner_can_mark_read(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.patch(self._detail_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())

    def test_cross_user_mark_read_is_denied_and_preserves_row(self):
        # Bob tries to mark Alice's notification read → 404 (existence not leaked).
        self.assert_denies_cross_user(
            self._detail_url(self.a1), self.bob, method="patch", data={}
        )
        self.assertTrue(Notification.objects.filter(id=self.a1.id).exists())

    def test_cross_user_cannot_see_via_list(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["message"] for row in data}, {"b-one"})
