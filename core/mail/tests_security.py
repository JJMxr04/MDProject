"""S-13: notification mark-read IDOR denial test.

A user must not be able to delete another user's notification by id.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.mail.models import Notification
from core.user.models import User




def _make_user(suffix: str) -> User:
    return User.objects.create_user(
        username=f"n_{suffix}",
        email=f"n_{suffix}@test.local",
        password="testpassword",
    )


class NotificationAccessTests(TestCase):
    # Mail notification urls are included under the core-portal namespace.
    URL_NAME = "core-portal:read_notifications"

    def test_user_cannot_mark_anothers_notification_read(self):
        victim = _make_user("victim")
        attacker = _make_user("attacker")
        notif = Notification.objects.create_notification(victim, "secret message")

        self.client.force_login(attacker)
        url = reverse(self.URL_NAME, args=[notif.id])
        resp = self.client.post(url, secure=True)

        self.assertEqual(resp.status_code, 404)  # denied, existence not leaked
        # And it must still exist — the attacker's call must not delete it.
        self.assertTrue(Notification.objects.filter(id=notif.id).exists())

    def test_owner_can_mark_own_notification_read(self):
        owner = _make_user("owner")
        notif = Notification.objects.create_notification(owner, "hello")

        self.client.force_login(owner)
        url = reverse(self.URL_NAME, args=[notif.id])

        # Marking it read deletes the notification.
        resp = self.client.post(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Notification.objects.filter(id=notif.id).exists())
