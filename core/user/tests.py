from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.auth import twofa
from core.match.tests.factories import make_user


class UserAdminPasswordTests(TestCase):
    """The user change form shows a reset link, never the password hash."""

    def setUp(self):
        self.staff = make_user("admin")
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.staff)
        self.target = make_user("target")

    def test_change_form_has_reset_link_but_no_hash_field(self):
        response = self.client.get(
            reverse("admin:core_user_user_change", args=[self.target.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset password")
        password_url = reverse(
            "admin:auth_user_password_change", args=[self.target.pk]
        )
        self.assertContains(response, password_url)
        # The ReadOnlyPasswordHashField widget is gone — no algorithm/hash
        # summary anywhere on the page.
        self.assertNotContains(response, "algorithm")
        self.assertNotContains(response, 'name="password"')

    def test_password_change_form_still_works(self):
        url = reverse("admin:auth_user_password_change", args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(url, {
            "password1": "n3w-Sup3r-secret!",
            "password2": "n3w-Sup3r-secret!",
        })
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("n3w-Sup3r-secret!"))


class UserAdmin2FATests(TestCase):
    """Per-user 2FA surface in the admin: status, reset (recovery), self-enroll."""

    def setUp(self):
        self.staff = make_user("admin2fa")
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.staff)
        self.target = make_user("target2fa")

    def _enroll(self, user):
        TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        twofa.issue_backup_codes(user)

    def test_change_form_shows_status_and_reset_button(self):
        self._enroll(self.target)
        resp = self.client.get(reverse("admin:core_user_user_change", args=[self.target.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Reset two-factor")
        self.assertContains(resp, "backup codes remaining")

    def test_change_form_shows_off_for_unenrolled(self):
        resp = self.client.get(reverse("admin:core_user_user_change", args=[self.target.pk]))
        self.assertContains(resp, "no confirmed device")

    def test_reset_removes_devices_and_emails(self):
        self._enroll(self.target)
        self.assertTrue(twofa.has_2fa(self.target))
        url = reverse("admin:core_user_user_reset_2fa", args=[self.target.pk])
        with patch("core.auth.twofa.send_security_email") as mock_email:
            resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(twofa.has_2fa(self.target))
        mock_email.assert_called_once_with(self.target, "disabled")

    def test_reset_requires_post(self):
        url = reverse("admin:core_user_user_reset_2fa", args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_self_enroll_link_only_on_own_row(self):
        own = self.client.get(reverse("admin:core_user_user_change", args=[self.staff.pk]))
        self.assertContains(own, "Set up my two-factor")
        other = self.client.get(reverse("admin:core_user_user_change", args=[self.target.pk]))
        self.assertNotContains(other, "Set up my two-factor")
