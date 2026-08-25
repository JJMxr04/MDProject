"""/api/v1/notifications/ security + behavior.

Covers the binding negative test ("User B → 404 for User A's object"),
list-scope, the unread badge count, and the read/clear lifecycle: reading or
clearing a notification deletes it outright.
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
        self.mark_all_url = reverse("api-v1:notifications-mark-all-read")
        self.clear_all_url = reverse("api-v1:notifications-clear-all")

    def _detail_url(self, notif):
        return reverse("api-v1:notifications-detail", args=[notif.id])

    def _clear_url(self, notif):
        return reverse("api-v1:notifications-clear", args=[notif.id])

    # --- list is scoped ---------------------------------------------------
    def test_list_returns_only_own_notifications(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        messages = {row["message"] for row in data}
        self.assertEqual(messages, {"a-one", "a-two"})

    def test_list_excludes_read_and_cleared(self):
        # Reading deletes the notification, so it drops out of the list.
        self.a1.mark_read()
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["message"] for row in data}, {"a-two"})

    def test_anonymous_list_is_401(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")

    # --- count is unread only --------------------------------------------
    def test_count_is_own_unread_count(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.count_url))
        self.assertEqual(data["count"], 1)

    def test_count_drops_when_handled(self):
        self.client.force_authenticate(self.alice)
        self.assertEqual(
            self.assert_success_envelope(self.client.get(self.count_url))["count"], 2
        )
        self.a1.mark_read()
        self.assertEqual(
            self.assert_success_envelope(self.client.get(self.count_url))["count"], 1
        )
        self.a2.clear()
        self.assertEqual(
            self.assert_success_envelope(self.client.get(self.count_url))["count"], 0
        )

    # --- mark read --------------------------------------------------------
    def test_mark_read_deletes(self):
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

    # --- clear ------------------------------------------------------------
    def test_clear_deletes(self):
        self.client.force_authenticate(self.alice)

        resp = self.client.post(self._clear_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())

    def test_cross_user_clear_is_denied(self):
        self.assert_denies_cross_user(
            self._clear_url(self.a1), self.bob, method="post", data={}
        )
        self.assertTrue(Notification.objects.filter(id=self.a1.id).exists())

    # --- bulk -------------------------------------------------------------
    def test_mark_all_read_deletes_all_own(self):
        self.client.force_authenticate(self.alice)

        data = self.assert_success_envelope(
            self.client.post(self.mark_all_url, {}, format="json")
        )
        self.assertEqual(data, {"deleted": 2})

        self.assertFalse(Notification.objects.filter(user=self.alice).exists())
        # Bob's row is untouched by Alice's sweep.
        self.assertTrue(Notification.objects.filter(id=self.b1.id).exists())

    def test_clear_all_deletes_all_own(self):
        self.client.force_authenticate(self.alice)

        data = self.assert_success_envelope(
            self.client.post(self.clear_all_url, {}, format="json")
        )
        self.assertEqual(data, {"deleted": 2})

        self.assertFalse(Notification.objects.filter(user=self.alice).exists())
        self.assertTrue(Notification.objects.filter(id=self.b1.id).exists())

    def test_bulk_requires_auth(self):
        resp = self.client.post(self.mark_all_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_user_cannot_see_via_list(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["message"] for row in data}, {"b-one"})
