"""Self-service 2FA: enrollment, login second-step, recovery.

Covers the security-critical paths: a confirmed device demands a code at the
next login (password alone no longer works), backup codes are single-use,
disable/regenerate require a live code (not just a session), the verify step
has its own rate-limit brake, and no password-only JWT obtain route exists.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django_otp.oath import totp
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.auth import twofa
from core.user.models import User


def _totp_now(device: TOTPDevice) -> str:
    """The TOTP code an authenticator app would show for ``device`` right now."""
    value = totp(device.bin_key, device.step, device.t0, device.digits, device.drift)
    return str(value).zfill(device.digits)


@override_settings(USE_AGGRIGATOR=False)
class TwoFactorTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dana", email="dana@test.local", password="rightpassword",
        )
        self.login_url = reverse("core-auth:login")
        self.verify_url = reverse("core-auth:2fa-verify")

    def _enroll(self, user=None) -> tuple[TOTPDevice, list[str]]:
        user = user or self.user
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        codes = twofa.issue_backup_codes(user)
        return device, codes


# ---------------------------------------------------------------- enrollment


class EnrollmentTests(TwoFactorTestBase):
    def test_setup_get_creates_unconfirmed_device_and_renders_qr(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core-auth:2fa-setup"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "<svg")
        self.assertTrue(TOTPDevice.objects.filter(user=self.user, confirmed=False).exists())
        # Not active until confirmed.
        self.assertFalse(twofa.has_2fa(self.user))

    def test_wrong_code_does_not_confirm_or_issue_backup_codes(self):
        self.client.force_login(self.user)
        self.client.get(reverse("core-auth:2fa-setup"))  # create device
        resp = self.client.post(reverse("core-auth:2fa-setup"), {"otp_token": "000000"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(twofa.has_2fa(self.user))
        self.assertEqual(twofa.backup_codes_remaining(self.user), 0)

    def test_right_code_confirms_issues_codes_and_emails(self):
        self.client.force_login(self.user)
        self.client.get(reverse("core-auth:2fa-setup"))
        device = TOTPDevice.objects.get(user=self.user, confirmed=False)

        with patch("core.auth.twofa.send_security_email") as mock_email:
            resp = self.client.post(
                reverse("core-auth:2fa-setup"), {"otp_token": _totp_now(device)},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(twofa.has_2fa(self.user))
        self.assertEqual(twofa.backup_codes_remaining(self.user), 10)
        # Codes are shown exactly once, on this response.
        self.assertContains(resp, "Backup codes")
        mock_email.assert_called_once_with(self.user, "enabled")


# ------------------------------------------------------------ login second-step


class LoginEnforcementTests(TwoFactorTestBase):
    def _login(self, password="rightpassword"):
        return self.client.post(
            self.login_url, {"username": "dana@test.local", "password": password},
        )

    def test_enrolled_user_lands_on_verify_not_logged_in(self):
        self._enroll()
        resp = self._login()
        self.assertRedirects(resp, self.verify_url, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIn("2fa_pending", self.client.session)

    def test_valid_totp_completes_login(self):
        device, _ = self._enroll()
        self._login()
        resp = self.client.post(self.verify_url, {"otp_token": _totp_now(device)})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.pk))
        self.assertNotIn("2fa_pending", self.client.session)

    def test_backup_code_completes_login_and_is_consumed(self):
        _, codes = self._enroll()
        self._login()
        resp = self.client.post(self.verify_url, {"otp_token": codes[0]})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.pk))
        self.assertEqual(twofa.backup_codes_remaining(self.user), 9)

    def test_expired_pending_falls_back_to_login(self):
        device, _ = self._enroll()
        self._login()
        # Age the pending stamp past the 5-minute TTL.
        session = self.client.session
        session["2fa_pending"]["ts"] = "2000-01-01T00:00:00+00:00"
        session.save()
        resp = self.client.post(self.verify_url, {"otp_token": _totp_now(device)})
        self.assertRedirects(resp, self.login_url, fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("2fa_pending", self.client.session)

    def test_unenrolled_user_logs_in_directly(self):
        resp = self._login()
        # No device → straight to the dashboard, fully logged in (regression).
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/2fa/", resp["Location"])
        self.assertEqual(str(self.client.session.get("_auth_user_id")), str(self.user.pk))

    def test_wrong_password_never_reaches_verify(self):
        self._enroll()
        resp = self._login(password="nope")
        self.assertEqual(resp.status_code, 200)  # form re-rendered
        self.assertNotIn("2fa_pending", self.client.session)


# ------------------------------------------------------------------ recovery


class DisableRegenerateTests(TwoFactorTestBase):
    def test_disable_requires_a_live_code(self):
        self._enroll()
        self.client.force_login(self.user)
        # Session alone (no code) must not strip 2FA.
        resp = self.client.post(reverse("core-auth:2fa-disable"), {"otp_token": ""})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(twofa.has_2fa(self.user))

    def test_disable_with_valid_code_removes_devices_and_emails(self):
        device, _ = self._enroll()
        self.client.force_login(self.user)
        with patch("core.auth.twofa.send_security_email") as mock_email:
            resp = self.client.post(
                reverse("core-auth:2fa-disable"), {"otp_token": _totp_now(device)},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(twofa.has_2fa(self.user))
        self.assertFalse(StaticDevice.objects.filter(user=self.user).exists())
        mock_email.assert_called_once_with(self.user, "disabled")

    def test_regenerate_replaces_codes(self):
        device, old_codes = self._enroll()
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("core-auth:2fa-regenerate"), {"otp_token": _totp_now(device)},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Backup codes")
        self.assertEqual(twofa.backup_codes_remaining(self.user), 10)
        # The old codes no longer validate.
        sd = twofa.static_device(self.user)
        live = set(sd.token_set.values_list("token", flat=True))
        self.assertEqual(live & set(old_codes), set())


class PageRenderTests(TwoFactorTestBase):
    def test_security_page_renders_for_unenrolled(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Enable two-factor authentication")

    def test_security_page_renders_for_enrolled(self):
        self._enroll()
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Regenerate")
        self.assertContains(resp, "Disable 2FA")

    def test_verify_get_renders_with_pending(self):
        self._enroll()
        self.client.post(self.login_url, {"username": "dana@test.local", "password": "rightpassword"})
        resp = self.client.get(self.verify_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Two-step verification")

    def test_verify_get_without_pending_redirects_to_login(self):
        resp = self.client.get(self.verify_url)
        self.assertRedirects(resp, self.login_url, fetch_redirect_response=False)


# --------------------------------------------------------------- rate limit


class VerifyRateLimitTests(TwoFactorTestBase):
    def test_verify_step_is_throttled(self):
        # The verify view counts every request per IP; the 11th in the window
        # is refused regardless of token validity (axes can't see this stage).
        for _ in range(10):
            resp = self.client.post(self.verify_url, {"otp_token": "000000"},
                                    REMOTE_ADDR="203.0.113.9")
            self.assertNotEqual(resp.status_code, 429)
        resp = self.client.post(self.verify_url, {"otp_token": "000000"},
                                REMOTE_ADDR="203.0.113.9")
        self.assertEqual(resp.status_code, 429)


# ------------------------------------------------------------ JWT bypass


class JwtBypassClosedTests(TestCase):
    def test_no_password_only_jwt_obtain_route_is_exposed(self):
        """A routed SimpleJWT token-obtain (or the legacy LoginViewSet) would
        let an enrolled user trade password→JWT and skip 2FA entirely. Assert
        none is wired (closed by absence)."""
        from django.urls import get_resolver
        from rest_framework_simplejwt.views import TokenViewBase

        from core.auth.viewsets import LoginViewSet

        def callbacks(resolver):
            for p in resolver.url_patterns:
                if hasattr(p, "url_patterns"):
                    yield from callbacks(p)
                else:
                    try:
                        yield p.callback
                    except Exception:  # noqa: BLE001
                        continue

        for cb in callbacks(get_resolver()):
            cls = getattr(cb, "cls", None) or getattr(cb, "view_class", None)
            if cls is None:
                continue
            self.assertFalse(
                issubclass(cls, TokenViewBase),
                f"SimpleJWT token-obtain route exposed: {cls}",
            )
            self.assertIsNot(cls, LoginViewSet, "legacy LoginViewSet is routed")
