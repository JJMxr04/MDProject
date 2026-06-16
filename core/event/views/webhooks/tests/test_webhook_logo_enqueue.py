"""Storing an event enqueues a logo fetch for each team lacking an ok logo."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.event.views.webhooks import sportsgameodds as wh


class WebhookLogoEnqueueTests(TestCase):
    def test_apply_enqueues_for_both_teams(self):
        view = wh.SportsGameOddsWebhookView()
        ev = {
            "event_id": "evt-1", "sport_id": "VOLLEYBALL", "league_id": "VNL",
            "start_time": "2026-06-13T18:00:00Z",
            "home_team": {
                "team_id": "USA", "league_id": "VNL", "name_long": "United States",
            },
            "away_team": {
                "team_id": "BRA", "league_id": "VNL", "name_long": "Brazil",
            },
        }
        with mock.patch.object(wh, "enqueue_team_logo") as enq:
            view._apply(ev, [])
        enq.assert_any_call("VNL:USA")
        enq.assert_any_call("VNL:BRA")
        self.assertEqual(enq.call_count, 2)
