"""Upcoming-event detail view: context carries a shared-matchup fixture."""
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.user.models import User

AGG_EVENT = {
    "id": "evt-1",
    "start_time": "2030-01-01T19:30:00+00:00",
    "status_type": "notstarted",
    "is_live": False, "is_finalized": False, "completed": False,
    "home_score": None, "away_score": None,
    "home_team": {"name_long": "Mavericks", "name": "Mavericks",
                  "logo_url": "/v1/teams/h/logo", "primary_color": "#1E40AF"},
    "away_team": {"name_long": "Celtics", "name": "Celtics",
                  "logo_url": "/v1/teams/a/logo", "primary_color": "#DC2626"},
    "league": {"name": "NBA"}, "sport": {"name": "basketball"},
    "markets": [],
}


@override_settings(
    USE_AGGRIGATOR=True,
    AGG_PUBLIC_BASE="http://agg.test",
)
class UpcomingDetailFixtureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ud", email="ud@example.com", password="pw-123456789")
        self.client.force_login(self.user)

    @mock.patch("core.portal.services.aggrigator_client.event_live_odds", return_value=None)
    @mock.patch("core.portal.services.aggrigator_client.event_probabilities", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_historical_stats", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_context", return_value={})
    @mock.patch("core.event.views.upcoming_event_detail._fetch_leagues", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail._fetch_sports", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail.AggrigatorClient")
    def test_context_fixture_absolutized_and_tinted(self, MockClient, *_):
        MockClient.return_value.get_event.return_value = AGG_EVENT
        url = reverse("core-portal:upcoming-events-detail", args=["evt-1"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        fixture = resp.context["fixture"]
        self.assertTrue(fixture["home"]["logo_url"].startswith("http"))
        self.assertIn("tint", fixture["home"])
        self.assertIn("tint", fixture["away"])
        self.assertEqual(fixture["home"]["tint"], "#1E40AF")
        # The team-logo <img> renders on the page.
        self.assertContains(resp, 'class="team-logo"')
