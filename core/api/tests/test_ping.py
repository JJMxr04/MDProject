"""Foundation smoke tests for the v1 spine (plan 10 — Phase 0 gate).

Proves: IsAuthenticated default, the success/error envelope shape, and CSRF
enforcement on a session-authed unsafe method.
"""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.api.tests.base import V1APITestCase


class PingEnvelopeTests(V1APITestCase):
    def setUp(self):
        self.url = reverse("api-v1:ping")

    def test_anonymous_get_is_401_with_error_envelope(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(response, code="not_authenticated")

    def test_authenticated_get_returns_success_envelope(self):
        user = self.make_user("ping")
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(response)
        self.assertTrue(data["pong"])
        self.assertEqual(data["user"], user.get_username())

    def test_authenticated_post_returns_success_envelope(self):
        # force_authenticate bypasses CSRF; this asserts POST is enveloped too.
        user = self.make_user("post")
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_success_envelope(response)


class PingCsrfTests(V1APITestCase):
    """SessionAuthentication must enforce CSRF on cookie-authed unsafe methods."""

    def setUp(self):
        self.url = reverse("api-v1:ping")
        self.user = self.make_user("csrf")
        self.user.set_password("testpassword")
        self.user.save()

    def test_session_post_without_csrf_token_is_forbidden(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)  # real session cookie, no CSRF token sent
        response = client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assert_error_envelope(response, code="forbidden")

    def test_session_get_does_not_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
