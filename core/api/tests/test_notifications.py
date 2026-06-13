"""Phase 1 pilot: /api/v1/notifications/ security + behavior (plan 07/10).

Covers the binding negative test ("User B → 404 for User A's object"),
list-scope, the unread badge count, and the read/clear lifecycle: a fresh
notification is stamped read or cleared; a second mark/clear action on an
already-handled notification deletes it.
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
        # The bell shows only fresh notifications; handled ones drop out so a
        # poll never resurfaces them.
        self.a1.mark_read()
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["message"] for row in data}, {"a-two"})

    def test_list_exposes_state_fields(self):
        # A fresh notification carries null state fields the client can read.
        self.client.force_authenticate(self.alice)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        row = next(r for r in data if r["message"] == "a-one")
        self.assertIn("read_at", row)
        self.assertIsNone(row["read_at"])
        self.assertIsNone(row["cleared_at"])

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
    def test_mark_read_stamps_then_second_call_deletes(self):
        self.client.force_authenticate(self.alice)

        resp = self.client.patch(self._detail_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.a1.refresh_from_db()
        self.assertIsNotNone(self.a1.read_at)

        # Second mark-read on an already-read row removes it.
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
    def test_clear_stamps_then_second_call_deletes(self):
        self.client.force_authenticate(self.alice)

        resp = self.client.post(self._clear_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.a1.refresh_from_db()
        self.assertIsNotNone(self.a1.cleared_at)

        resp = self.client.post(self._clear_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())

    def test_clear_after_read_deletes(self):
        # Already-read → clear treats it as handled and deletes it.
        self.client.force_authenticate(self.alice)
        self.client.patch(self._detail_url(self.a1), {}, format="json")
        resp = self.client.post(self._clear_url(self.a1), {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())

    def test_cross_user_clear_is_denied(self):
        self.assert_denies_cross_user(
            self._clear_url(self.a1), self.bob, method="post", data={}
        )
        self.assertTrue(Notification.objects.filter(id=self.a1.id).exists())

    # --- bulk -------------------------------------------------------------
    def test_mark_all_read_marks_fresh_and_drops_handled(self):
        self.a1.mark_read()  # already handled -> should be deleted by sweep
        self.client.force_authenticate(self.alice)

        data = self.assert_success_envelope(
            self.client.post(self.mark_all_url, {}, format="json")
        )
        self.assertEqual(data, {"marked": 1, "deleted": 1})

        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())
        self.a2.refresh_from_db()
        self.assertIsNotNone(self.a2.read_at)
        # Bob's row is untouched by Alice's sweep.
        self.assertTrue(Notification.objects.filter(id=self.b1.id).exists())

    def test_clear_all_clears_fresh_and_drops_handled(self):
        self.a1.clear()  # already handled -> deleted by sweep
        self.client.force_authenticate(self.alice)

        data = self.assert_success_envelope(
            self.client.post(self.clear_all_url, {}, format="json")
        )
        self.assertEqual(data, {"cleared": 1, "deleted": 1})

        self.assertFalse(Notification.objects.filter(id=self.a1.id).exists())
        self.a2.refresh_from_db()
        self.assertIsNotNone(self.a2.cleared_at)

    def test_bulk_requires_auth(self):
        resp = self.client.post(self.mark_all_url, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_user_cannot_see_via_list(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.list_url))
        self.assertEqual({row["message"] for row in data}, {"b-one"})
