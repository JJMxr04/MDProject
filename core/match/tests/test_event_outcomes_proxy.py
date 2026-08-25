"""Tests for the ``event_outcomes`` proxy view."""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from core.event.providers.aggregator_client import AggrigatorError
from core.match.tests.factories import make_user


@override_settings(USE_AGGRIGATOR=True)
class EventOutcomesProxyTests(TestCase):
    def setUp(self):
        self.user = make_user("ops")
        self.client.force_login(self.user)
        self.event_id = "evt-test-xyz"
        self.url = reverse(
            "core-portal:portal-match-event-outcomes",
            kwargs={"event_id": self.event_id},
        )

    def _stub(self, body):
        return patch(
            "core.match.views.eventOutcome.AggrigatorClient",
            return_value=type("C", (), {
                "get_event": lambda _self, _id, include_markets=True: body,
            })(),
        )

    def test_url_pattern_accepts_string_event_id(self):
        # Pre-fix this URL was <int:event_id> and would 404 alphanumeric
        # SGO eventIDs. The view should resolve.
        from django.urls import resolve
        match = resolve(self.url)
        self.assertEqual(match.kwargs["event_id"], self.event_id)

    def test_proxies_aggregator_response(self):
        body = {
            "markets": [
                {"market_id": "m1", "category": "MONEYLINE", "selections": []},
            ],
            "odds_meta": {"stale": False},
        }
        with self._stub(body):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["event"]["event_id"], self.event_id)
        self.assertEqual(len(data["event"]["markets"]), 1)

    def test_selections_get_humanized_display_label(self):
        """Each selection carries a plain-English ``display_label`` so the
        duel/pick UIs never surface the raw 'home home' moneyline label."""
        body = {
            "home_team": {"name": "Detroit Red Wings"},
            "away_team": {"name": "Boston Bruins"},
            "markets": [
                {
                    "market_id": "m1", "category": "MONEYLINE", "scope": "FULL_GAME",
                    "selections": [
                        {"id": "s-home", "type": "HOME", "label": "home home"},
                        {"id": "s-away", "type": "AWAY", "label": "away away"},
                    ],
                },
            ],
            "odds_meta": {"stale": False},
        }
        with self._stub(body):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        sels = r.json()["event"]["markets"][0]["selections"]
        by_id = {s["selection_id"]: s for s in sels}
        self.assertEqual(by_id["s-home"]["display_label"], "Detroit Red Wings to win")
        self.assertEqual(by_id["s-away"]["display_label"], "Boston Bruins to win")
        # Raw label is preserved untouched alongside the humanized one.
        self.assertEqual(by_id["s-home"]["label"], "home home")

    def test_aggregator_error_returns_503(self):
        with patch(
            "core.match.views.eventOutcome.AggrigatorClient",
            return_value=type("C", (), {
                "get_event": lambda *_, **__: (_ for _ in ()).throw(
                    AggrigatorError("simulated outage"),
                ),
            })(),
        ):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 503)

    def test_aggregator_404_returns_404(self):
        with self._stub(None):
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 404)
