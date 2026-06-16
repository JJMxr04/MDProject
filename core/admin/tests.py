from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class BackfillLogosViewTests(TestCase):
    def setUp(self):
        self.url = reverse("core-admin:admin_backfill_logos")
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw-123456789",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

    def test_get_is_rejected_post_only(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    def test_logged_in_non_staff_is_blocked(self):
        non_staff = User.objects.create_user(
            username="member", email="member@example.com", password="pw-123456789",
        )
        # default is_staff=False
        self.client.force_login(non_staff)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    @patch("core.admin.views.run_backfill_team_logos", return_value=7)
    def test_staff_post_enqueues_and_flashes_count(self, mock_backfill):
        self.client.force_login(self.staff)
        resp = self.client.post(self.url, follow=True)
        mock_backfill.assert_called_once_with()
        self.assertEqual(resp.redirect_chain[-1][0], reverse("core-admin:admin_status"))
        self.assertIn("queued 7 team-logo", resp.content.decode())
