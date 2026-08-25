"""/api/v1/analytics/events/<id>/ — event analytics (free, auth-only).

The analytics dashboard is free: this endpoint requires
auth (anon -> 401) but no PRO entitlement (any authenticated user -> 200).
The aggregator helpers are patched so every test is hermetic.
"""

from __future__ import annotations

from unittest import mock

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase

MODULE = "core.api.v1.analytics.aggrigator_client"


def _stub_aggrigator(**overrides):
    """Patch the four event-analytics helpers the view calls.

    Returns a context manager that patches all four at once; pass overrides
    (e.g. ``event_context={...}``) to shape individual sections.
    """
    defaults = {
        "event_context": {
            "form_into_match": {"home": "WWLDW"},
            "form_detail": {},
            "h2h_last_5": [{"id": "x"}],
            "h2h_aggregate": {"home_wins": 3},
        },
        "event_historical_stats": {"is_finalized": False},
        "event_probabilities": {"p_home": 0.5, "p_draw": 0.3, "p_away": 0.2},
        "event_live_odds": {"markets": []},
    }
    defaults.update(overrides)
    return mock.patch.multiple(
        MODULE,
        event_context=mock.Mock(return_value=defaults["event_context"]),
        event_historical_stats=mock.Mock(
            return_value=defaults["event_historical_stats"]
        ),
        event_probabilities=mock.Mock(return_value=defaults["event_probabilities"]),
        event_live_odds=mock.Mock(return_value=defaults["event_live_odds"]),
    )


class EventAnalyticsApiTests(V1APITestCase):
    def setUp(self):
        self.user = self.make_user("viewer")
        self.url = reverse("api-v1:analytics-event", args=["evt_1"])

    def test_anonymous_is_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")

    def test_authenticated_returns_200_no_subscription_needed(self):
        # Analytics is free: any authenticated user, no sub, gets 200.
        self.client.force_authenticate(self.user)
        with _stub_aggrigator():
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual(data["event_id"], "evt_1")
        self.assertEqual(data["form_into_match"], {"home": "WWLDW"})
        self.assertEqual(data["h2h_last_5"], [{"id": "x"}])
        self.assertFalse(data["is_finalized"])

    def test_serializer_does_not_leak_upstream_fields(self):
        self.client.force_authenticate(self.user)
        leaky = {
            "form_into_match": {},
            "h2h_last_5": [],
            "secret": "x",
            "internal_id": 99,
        }
        with _stub_aggrigator(event_context=leaky):
            data = self.client.get(self.url).json()["data"]
        self.assertNotIn("secret", data)
        self.assertNotIn("internal_id", data)
        self.assertEqual(
            set(data.keys()),
            {
                "event_id",
                "is_finalized",
                "form_into_match",
                "form_detail",
                "h2h_last_5",
                "h2h_aggregate",
                "historical_stats",
                "model_prob",
                "live_odds",
            },
        )

    def test_aggregator_outage_is_502_envelope(self):
        # All four helpers return {} (their transport-failure shape).
        self.client.force_authenticate(self.user)
        with _stub_aggrigator(
            event_context={},
            event_historical_stats={},
            event_probabilities={},
            event_live_odds={},
        ):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assert_error_envelope(resp, code="upstream_unavailable")
