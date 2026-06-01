"""django-axes brute-force lockout proof (S-9).

Asserts that repeated failed logins on the server-rendered login view lock the
(IP, username) pair, and that the lockout then blocks even a correct password
until cooloff. USE_AGGRIGATOR is disabled so creating the victim user doesn't try
to reach the aggrigator over HTTP.
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from core.user.models import User

_LIMIT = 3


@override_settings(USE_AGGRIGATOR=False, AXES_FAILURE_LIMIT=_LIMIT)
class AuthLockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="victim",
            email="victim@test.local",
            password="rightpassword",
        )
        self.url = reverse("core-auth:login")

    def _attempt(self, password):
        return self.client.post(
            self.url,
            {"username": "victim@test.local", "password": password},
        )

    def test_repeated_failures_lock_the_account(self):
        statuses = [self._attempt("wrongpassword").status_code for _ in range(_LIMIT + 1)]
        # Once the failure limit is reached, axes returns AXES_HTTP_RESPONSE_CODE (429).
        self.assertIn(429, statuses, f"expected a 429 lockout in {statuses}")

    def test_lockout_blocks_even_correct_password(self):
        for _ in range(_LIMIT + 1):
            self._attempt("wrongpassword")
        # Correct credentials are now refused too — the lock is on (ip, username).
        locked = self._attempt("rightpassword")
        self.assertEqual(locked.status_code, 429)
