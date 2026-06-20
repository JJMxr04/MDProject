"""Email preference + unsubscribe tests (plan §7.5 item 4).

Engagement emails route through ``Emails._notify``: in-app Notification
always writes (unless the caller passes ``in_app=False``, as the invite
emails do); the email job only defers when ``User.email_notifications``
is on, and its context carries the signed unsubscribe URL.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from procrastinate.contrib.django.models import ProcrastinateJob

from core.mail.models import Emails, Notification
from core.mail.unsubscribe import make_token, read_token
from core.match.tests.factories import make_user


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


class NotifyPreferenceTests(TestCase):
    def test_opted_in_user_gets_notification_and_email_with_unsub_url(self):
        user = make_user("optin")
        before = _email_jobs().count()

        Emails.send_opponent_pick_notification(user, "rival")

        self.assertTrue(Notification.objects.filter(user=user).exists())
        jobs = _email_jobs()
        self.assertEqual(jobs.count(), before + 1)
        job = jobs.order_by("-id").first()
        self.assertEqual(job.args["recipient"], user.email)
        self.assertIn("unsubscribe_url", job.args["context"])
        self.assertIn("/auth/unsubscribe/", job.args["context"]["unsubscribe_url"])

    def test_opted_out_user_gets_notification_but_no_email(self):
        user = make_user("optout")
        user.email_notifications = False
        user.save(update_fields=["email_notifications"])
        before = _email_jobs().count()

        Emails.send_opponent_pick_notification(user, "rival")

        self.assertTrue(Notification.objects.filter(user=user).exists())
        self.assertEqual(_email_jobs().count(), before)


class UnsubscribeViewTests(TestCase):
    def _url(self, token):
        return reverse("core-auth:unsubscribe", args=[token])

    def test_get_unsubscribes(self):
        user = make_user("unsub")
        resp = self.client.get(self._url(make_token(user)), secure=True)

        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.email_notifications)

    def test_one_click_post_unsubscribes(self):
        user = make_user("oneclick")
        resp = self.client.post(
            self._url(make_token(user)),
            {"List-Unsubscribe": "One-Click"},
            secure=True,
        )

        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.email_notifications)

    def test_resubscribe(self):
        user = make_user("resub")
        user.email_notifications = False
        user.save(update_fields=["email_notifications"])

        resp = self.client.post(
            self._url(make_token(user)), {"action": "resubscribe"}, secure=True,
        )

        self.assertEqual(resp.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.email_notifications)

    def test_garbage_token_404s_without_state_change(self):
        resp = self.client.get(self._url("not-a-real-token"), secure=True)
        self.assertEqual(resp.status_code, 404)

    def test_token_roundtrip_and_tamper(self):
        user = make_user("token")
        token = make_token(user)
        self.assertEqual(read_token(token), str(user.public_id))
        self.assertIsNone(read_token(token + "x"))
