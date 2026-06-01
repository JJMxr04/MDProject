"""v1 test base: envelope assertions + the reusable cross-user denial helper.

Plan 03/10 binding rule: *every* v1 resource endpoint ships with a negative test
("User B -> 404 for User A's object"). ``assert_denies_cross_user`` is that test
in one call, so the rule is cheap to honor and hard to forget.
"""

from __future__ import annotations

import uuid

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from core.user.models import User


# Creating a User fires the billing post_save signal, which mirrors the user into
# the aggrigator over HTTP when USE_AGGRIGATOR=True (the local .env). Tests must
# be hermetic, so disable that integration for the whole v1 suite.
@override_settings(USE_AGGRIGATOR=False)
class V1APITestCase(APITestCase):
    # --- factories -------------------------------------------------------
    def make_user(self, suffix: str = "") -> User:
        suffix = suffix or uuid.uuid4().hex[:8]
        return User.objects.create_user(
            username=f"u_{suffix}",
            email=f"u_{suffix}@test.local",
            password="testpassword",
        )

    # --- envelope assertions --------------------------------------------
    # NB: read the *rendered* body via response.json(), not response.data —
    # the success envelope is applied by EnvelopeJSONRenderer at render time, so
    # response.data still holds the raw view payload.
    def assert_success_envelope(self, response):
        body = response.json()
        self.assertIn("data", body, body)
        self.assertIn("meta", body, body)
        meta = body["meta"]
        self.assertTrue(str(meta.get("request_id", "")).startswith("req_"), meta)
        self.assertIn("generated_at", meta)
        return body["data"]

    def assert_error_envelope(self, response, code: str | None = None):
        body = response.json()
        self.assertIn("error", body, body)
        self.assertIn("meta", body, body)
        err = body["error"]
        self.assertIn("message", err)
        self.assertIn("details", err)
        if code is not None:
            self.assertEqual(err.get("code"), code, err)
        return err

    # --- the reusable cross-user denial -------------------------------
    def assert_denies_cross_user(self, url, other_user, *, method: str = "get", data=None):
        """Authenticate as ``other_user`` and assert they cannot reach ``url``.

        Passes if the response is 404 (preferred — existence not leaked) or 403.
        Never allow a 2xx for a non-owned object.
        """
        self.client.force_authenticate(user=other_user)
        try:
            response = getattr(self.client, method.lower())(url, data=data, format="json")
        finally:
            self.client.force_authenticate(user=None)
        self.assertIn(
            response.status_code,
            (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN),
            f"cross-user {method.upper()} {url} returned {response.status_code}, "
            f"expected 404/403:\n{getattr(response, 'data', response.content)}",
        )
        return response
