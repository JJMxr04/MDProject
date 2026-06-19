from __future__ import annotations

from django.test import TestCase, override_settings

from core.auth.models import KnownLoginFingerprint, LoginEvent
from core.auth.services.login_security import summarize_user_agent, upsert_fingerprint
from core.user.models import User


@override_settings(USE_AGGRIGATOR=False)
class LoginEventModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mia", email="mia@test.local", password="pw",
        )

    def test_login_event_defaults_and_str(self):
        ev = LoginEvent.objects.create(
            user=self.user,
            event_type=LoginEvent.SUCCESS,
            ip_address="203.0.113.7",
            country="US",
            user_agent="Mozilla/5.0",
            device_label="Chrome on macOS",
            session_key="abc123",
        )
        self.assertFalse(ev.is_new_device)
        self.assertFalse(ev.is_new_location)
        self.assertIsNotNone(ev.created_at)
        self.assertIn("success", str(ev))

    def test_fingerprint_unique_per_user_country_device(self):
        KnownLoginFingerprint.objects.create(
            user=self.user, country="US", device_label="Chrome on macOS",
        )
        with self.assertRaises(Exception):
            KnownLoginFingerprint.objects.create(
                user=self.user, country="US", device_label="Chrome on macOS",
            )


@override_settings(USE_AGGRIGATOR=False)
class UserAgentSummaryTests(TestCase):
    def test_chrome_on_macos(self):
        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
        self.assertEqual(summarize_user_agent(ua), "Chrome on macOS")

    def test_safari_on_iphone(self):
        ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        self.assertEqual(summarize_user_agent(ua), "Safari on iOS")

    def test_firefox_on_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        self.assertEqual(summarize_user_agent(ua), "Firefox on Windows")

    def test_blank_is_unknown(self):
        self.assertEqual(summarize_user_agent(""), "Unknown device")
        self.assertEqual(summarize_user_agent("garbage-string"), "Unknown device")


@override_settings(USE_AGGRIGATOR=False)
class FingerprintUpsertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="leo", email="leo@test.local", password="pw",
        )

    def test_first_login_is_not_new(self):
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Chrome on macOS")
        self.assertFalse(new_dev)
        self.assertFalse(new_loc)
        self.assertEqual(KnownLoginFingerprint.objects.filter(user=self.user).count(), 1)

    def test_same_device_again_is_not_new(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Chrome on macOS")
        self.assertFalse(new_dev)
        self.assertFalse(new_loc)
        self.assertEqual(KnownLoginFingerprint.objects.filter(user=self.user).count(), 1)

    def test_new_device_known_country(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Safari on iOS")
        self.assertTrue(new_dev)
        self.assertFalse(new_loc)

    def test_new_country_known_device(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "GB", "Chrome on macOS")
        self.assertFalse(new_dev)  # same device label, already seen
        self.assertTrue(new_loc)   # GB never seen before


from unittest.mock import patch
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.test import RequestFactory


@override_settings(USE_AGGRIGATOR=False)
class SignalRecordingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", email="ada@test.local", password="pw",
        )
        self.rf = RequestFactory()

    def _req(self, ua="Mozilla/5.0 (Windows NT 10.0) Firefox/121.0", country="US", ip="203.0.113.9"):
        req = self.rf.get("/")
        req.META["HTTP_USER_AGENT"] = ua
        req.META["HTTP_CF_IPCOUNTRY"] = country
        req.META["HTTP_CF_CONNECTING_IP"] = ip
        # RequestFactory has no session; attach a fake with a key.
        class _S:
            session_key = "sess-key-1"
        req.session = _S()
        return req

    def test_login_signal_writes_success_event(self):
        user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
        ev = LoginEvent.objects.get(user=self.user, event_type=LoginEvent.SUCCESS)
        self.assertEqual(ev.country, "US")
        self.assertEqual(ev.ip_address, "203.0.113.9")
        self.assertEqual(ev.device_label, "Firefox on Windows")
        self.assertEqual(ev.session_key, "sess-key-1")

    def test_second_login_new_device_flagged(self):
        user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
        user_logged_in.send(
            sender=self.user.__class__,
            request=self._req(ua="Mozilla/5.0 (iPhone) Safari/604.1"),
            user=self.user,
        )
        latest = LoginEvent.objects.filter(user=self.user, event_type=LoginEvent.SUCCESS).first()
        self.assertTrue(latest.is_new_device)

    def test_failed_login_signal_writes_failed_event(self):
        user_login_failed.send(
            sender=self.user.__class__,
            credentials={"username": "ada@test.local"},
            request=self._req(),
        )
        self.assertTrue(
            LoginEvent.objects.filter(user=self.user, event_type=LoginEvent.FAILED).exists()
        )

    def test_signal_swallows_write_errors(self):
        with patch("core.auth.services.login_security.LoginEvent.objects.create",
                   side_effect=RuntimeError("db down")):
            # Must not raise into the auth flow.
            user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
