"""event_context rewrites every nested team logo_url to MDProject's proxy.

Aggregator analytics payloads (h2h_last_5, form blocks) carry raw
``/v1/teams/{id}/logo`` URLs. Those reach the browser via the detail page's
json_script blob and the portal analytics API, so they must be rewritten to
the same-origin proxy or they'd hit the (key-gated) aggregator directly.
"""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from core.portal.services import aggrigator_client


def _proxy(team_id):
    return reverse("team-logo", kwargs={"team_id": team_id})


class EventContextLogoProxyTests(SimpleTestCase):
    def test_nested_logo_urls_rewritten_to_proxy(self):
        raw = {
            "h2h_last_5": [
                {
                    "home_team": {"logo_url": "/v1/teams/MLB:3641/logo"},
                    "away_team": {"logo_url": "http://agg:8001/v1/teams/MLB:3652/logo"},
                },
            ],
            "form_detail": {
                "home": {"recent": [{"opponent": {"logo_url": "/v1/teams/MLB:3629/logo"}}]},
            },
            "h2h_aggregate": {"played": 5},
        }
        with mock.patch.object(aggrigator_client, "_get", return_value=raw):
            out = aggrigator_client.event_context("evt-1")

        self.assertEqual(out["h2h_last_5"][0]["home_team"]["logo_url"], _proxy("MLB:3641"))
        self.assertEqual(out["h2h_last_5"][0]["away_team"]["logo_url"], _proxy("MLB:3652"))
        self.assertEqual(
            out["form_detail"]["home"]["recent"][0]["opponent"]["logo_url"],
            _proxy("MLB:3629"),
        )
        # Non-logo data is left untouched.
        self.assertEqual(out["h2h_aggregate"]["played"], 5)

    def test_null_logo_url_left_as_none(self):
        raw = {"h2h_last_5": [{"home_team": {"logo_url": None}}]}
        with mock.patch.object(aggrigator_client, "_get", return_value=raw):
            out = aggrigator_client.event_context("evt-1")
        self.assertIsNone(out["h2h_last_5"][0]["home_team"]["logo_url"])

    def test_transport_failure_returns_empty_dict(self):
        with mock.patch.object(aggrigator_client, "_get", return_value="not-a-dict"):
            self.assertEqual(aggrigator_client.event_context("evt-1"), {})
