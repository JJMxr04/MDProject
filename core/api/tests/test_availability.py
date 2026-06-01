"""/api/v1/availability/ — catalog (sports/leagues/bookmakers/markets).

Reference data, not user-scoped: the same catalog for every authenticated
user. The aggregator client is patched so tests stay hermetic.
"""

from __future__ import annotations

from unittest import mock

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase

CLIENT = "core.api.v1.availability.AggrigatorClient"


def _fake_client(**overrides):
    client = mock.Mock()
    client.get_sports.return_value = overrides.get(
        "sports", [{"id": "soccer", "name": "Soccer"}]
    )
    client.get_leagues.return_value = overrides.get(
        "leagues", [{"id": "epl", "name": "EPL", "sport_id": "soccer"}]
    )
    client.get_bookmakers.return_value = overrides.get(
        "bookmakers", [{"id": "dk", "name": "DraftKings"}]
    )
    client.get_market_types.return_value = overrides.get(
        "market_types", ["MONEYLINE"]
    )
    return client


class AvailabilityApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.url = reverse("api-v1:availability")

    def test_anonymous_is_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")

    def test_returns_flat_catalog(self):
        self.client.force_authenticate(self.alice)
        with mock.patch(CLIENT, return_value=_fake_client()):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        kinds = {row["kind"] for row in data}
        self.assertEqual(kinds, {"sport", "league", "bookmaker", "market_type"})
        league = next(r for r in data if r["kind"] == "league")
        self.assertEqual(league["id"], "epl")
        self.assertEqual(league["sport_id"], "soccer")
        market = next(r for r in data if r["kind"] == "market_type")
        self.assertEqual(market["name"], "MONEYLINE")

    def test_response_is_paginated(self):
        self.client.force_authenticate(self.alice)
        with mock.patch(CLIENT, return_value=_fake_client()):
            body = self.client.get(self.url).json()
        self.assertIn("page", body["meta"])
        self.assertIn("total", body["meta"])

    def test_serializer_does_not_leak_extra_fields(self):
        self.client.force_authenticate(self.alice)
        leaky = [{"id": "soccer", "name": "Soccer", "secret": "x"}]
        with mock.patch(CLIENT, return_value=_fake_client(sports=leaky)):
            data = self.client.get(self.url).json()["data"]
        sport = next(r for r in data if r["kind"] == "sport")
        self.assertEqual(set(sport.keys()), {"kind", "id", "name", "sport_id"})

    def test_aggregator_outage_degrades_to_empty(self):
        from core.event.providers.aggregator_client import AggrigatorError

        self.client.force_authenticate(self.alice)
        broken = mock.Mock()
        broken.get_sports.side_effect = AggrigatorError("down")
        with mock.patch(CLIENT, return_value=broken):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(self.assert_success_envelope(resp), [])
