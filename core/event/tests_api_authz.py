"""The legacy /api/ event endpoints must require authentication.

Proves anonymous callers are denied (was AllowAny) and an authenticated caller
gets past the auth gate. USE_AGGRIGATOR is disabled so creating the test user
doesn't reach the aggrigator over HTTP.
"""

from __future__ import annotations

import uuid

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.user.models import User

_DENIED = (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@override_settings(USE_AGGRIGATOR=False)
class EventApiRequiresAuthTests(APITestCase):
    def setUp(self):
        self.paths = [
            "/api/events",
            "/api/events/abc123",
            "/api/events/abc123/markets",
            "/api/selections/some-selection-id/movement",
        ]

    def test_anonymous_get_is_denied_on_every_event_endpoint(self):
        for path in self.paths:
            resp = self.client.get(path)
            self.assertIn(
                resp.status_code, _DENIED,
                f"{path} returned {resp.status_code}, expected auth denial",
            )

    def test_anonymous_post_slips_is_denied(self):
        resp = self.client.post("/api/slips", {"legs": []}, format="json")
        self.assertIn(resp.status_code, _DENIED)

    def test_authenticated_caller_passes_the_auth_gate(self):
        user = User.objects.create_user(
            username=f"u_{uuid.uuid4().hex[:8]}",
            email=f"u_{uuid.uuid4().hex[:8]}@test.local",
            password="testpassword",
        )
        self.client.force_authenticate(user=user)
        # Missing ?sport= -> 400 from the view itself, i.e. auth passed (not 401/403).
        resp = self.client.get("/api/events")
        self.assertNotIn(resp.status_code, _DENIED)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
