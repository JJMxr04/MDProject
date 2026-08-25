"""Rate-limit + enumeration tests for the public auth surface.

The waitlist and register form views are anonymous and send an email per
submission; before this they had no throttle and their duplicate/approval
errors leaked list membership.
"""

from __future__ import annotations

from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.auth.models.waitlist import WaitlistEntry
from core.ratelimit import rate_limit


class RateLimitDecoratorTests(TestCase):
    def _view(self, limit=2, per="ip"):
        @rate_limit("test-scope", limit, 60, per=per)
        def view(request):
            return JsonResponse({"ok": True})

        return view

    def test_blocks_after_limit_and_sets_retry_after(self):
        view = self._view(limit=2)
        rf = RequestFactory()

        for _ in range(2):
            resp = view(rf.post("/x", REMOTE_ADDR="10.1.1.1"))
            self.assertEqual(resp.status_code, 200)

        resp = view(rf.post("/x", REMOTE_ADDR="10.1.1.1"))
        self.assertEqual(resp.status_code, 429)
        self.assertIn("Retry-After", resp)

    def test_buckets_are_per_ip(self):
        view = self._view(limit=1)
        rf = RequestFactory()

        self.assertEqual(view(rf.post("/x", REMOTE_ADDR="10.2.2.1")).status_code, 200)
        self.assertEqual(view(rf.post("/x", REMOTE_ADDR="10.2.2.1")).status_code, 429)
        # A different client is unaffected.
        self.assertEqual(view(rf.post("/x", REMOTE_ADDR="10.2.2.2")).status_code, 200)


class WaitlistFormTests(TestCase):
    URL = "/auth/waitlist/"

    def _post(self, email, **extra):
        return self.client.post(
            self.URL, {"email": email, "full_name": "Test Person"}, secure=True, **extra
        )

    def test_sixth_submission_throttled(self):
        for i in range(5):
            resp = self._post(f"wl{i}@test.local")
            self.assertEqual(resp.status_code, 302, f"submission {i} should pass")
        resp = self._post("wl5@test.local")
        self.assertEqual(resp.status_code, 429)

    def test_duplicate_email_indistinguishable_and_single_row(self):
        first = self._post("dup@test.local")
        second = self._post("dup@test.local")

        # Same redirect either way — list membership is not confirmable.
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(
            WaitlistEntry.objects.filter(email="dup@test.local").count(), 1
        )


class RegisterFormThrottleTests(TestCase):
    URL = "/auth/register/"

    def test_sixth_submission_throttled(self):
        for i in range(5):
            resp = self.client.post(self.URL, {"email": f"r{i}@test.local"}, secure=True)
            # Invalid form (missing fields) — re-rendered, not throttled.
            self.assertEqual(resp.status_code, 200, f"submission {i} should pass")
        resp = self.client.post(self.URL, {"email": "r5@test.local"}, secure=True)
        self.assertEqual(resp.status_code, 429)


class PasswordResetThrottleTests(TestCase):
    def test_sixth_submission_throttled(self):
        url = reverse("reset_password")
        for i in range(5):
            resp = self.client.post(url, {"email": f"pw{i}@test.local"}, secure=True)
            self.assertIn(resp.status_code, (200, 302), f"submission {i} should pass")
        resp = self.client.post(url, {"email": "pw5@test.local"}, secure=True)
        self.assertEqual(resp.status_code, 429)
