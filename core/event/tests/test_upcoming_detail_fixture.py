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
    def test_context_fixture_proxied_and_tinted(self, MockClient, *_):
        MockClient.return_value.get_event.return_value = AGG_EVENT
        url = reverse("core-portal:upcoming-events-detail", args=["evt-1"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        fixture = resp.context["fixture"]
        # Logo points at MDProject's same-origin proxy, not the aggregator.
        self.assertEqual(
            fixture["home"]["logo_url"],
            reverse("team-logo", kwargs={"team_id": "h"}),
        )
        self.assertIn("tint", fixture["home"])
        self.assertIn("tint", fixture["away"])
        self.assertEqual(fixture["home"]["tint"], "#1E40AF")
        # The team-logo <img> renders on the page.
        self.assertContains(resp, 'class="team-logo"')


@override_settings(
    USE_AGGRIGATOR=True,
    AGG_PUBLIC_BASE="http://agg.test",
)
class WinProbContextTests(TestCase):
    """The hero win-probability bars are driven by a ``win_prob`` context
    dict derived from the model probabilities. It is present only when the
    model returned probabilities (soccer-only); otherwise it is ``None`` so
    the template hides the bars."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="wp", email="wp@example.com", password="pw-123456789")
        self.client.force_login(self.user)

    @mock.patch("core.portal.services.aggrigator_client.event_live_odds", return_value=None)
    @mock.patch("core.portal.services.aggrigator_client.event_probabilities")
    @mock.patch("core.portal.services.aggrigator_client.event_historical_stats", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_context", return_value={})
    @mock.patch("core.event.views.upcoming_event_detail._fetch_leagues", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail._fetch_sports", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail.AggrigatorClient")
    def test_win_prob_present_when_model_prob(self, MockClient, _sp, _lg, _ctx, _hist, mock_prob, _odds):
        MockClient.return_value.get_event.return_value = AGG_EVENT
        mock_prob.return_value = {"p_home": 0.62, "p_draw": 0.0, "p_away": 0.38}
        url = reverse("core-portal:upcoming-events-detail", args=["evt-1"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["win_prob"], {
            "p_home": 0.62, "p_away": 0.38, "home_pct": 62, "away_pct": 38,
        })

    @mock.patch("core.portal.services.aggrigator_client.event_live_odds", return_value=None)
    @mock.patch("core.portal.services.aggrigator_client.event_probabilities", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_historical_stats", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_context", return_value={})
    @mock.patch("core.event.views.upcoming_event_detail._fetch_leagues", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail._fetch_sports", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail.AggrigatorClient")
    def test_win_prob_absent_when_no_model(self, MockClient, *_):
        MockClient.return_value.get_event.return_value = AGG_EVENT
        url = reverse("core-portal:upcoming-events-detail", args=["evt-1"])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["win_prob"])


AGG_EVENT_RICH = {
    **AGG_EVENT,
    "markets": [{
        "category": "MONEYLINE", "type": "Moneyline", "line": None,
        "is_live": False, "suspended": False, "scope": "FULL_GAME",
        "selections": [
            {"settlement_status": "PENDING", "odds": {"american": -145, "decimal": 1.69}, "by_bookmaker": []},
            {"settlement_status": "PENDING", "odds": {"american": 125, "decimal": 2.25}, "by_bookmaker": []},
        ],
    }],
}


@override_settings(
    USE_AGGRIGATOR=True,
    AGG_PUBLIC_BASE="http://agg.test",
)
class DetailPageStructureTests(TestCase):
    """The redesigned page: two-column layout, CSS-only tabs, hero countdown,
    win-prob bars, and the Event Info + Challenge rail."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="st", email="st@example.com", password="pw-123456789")
        self.client.force_login(self.user)

    def _get(self):
        return self.client.get(reverse("core-portal:upcoming-events-detail", args=["evt-1"]))

    @mock.patch("core.portal.services.aggrigator_client.event_live_odds", return_value=None)
    @mock.patch("core.portal.services.aggrigator_client.event_probabilities",
                return_value={"p_home": 0.62, "p_draw": 0.0, "p_away": 0.38})
    @mock.patch("core.portal.services.aggrigator_client.event_historical_stats", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_context",
                return_value={"h2h_aggregate": {"played": 5, "home_team_wins": 3,
                                                 "away_team_wins": 2, "draws": 0},
                              "h2h_last_5": []})
    @mock.patch("core.event.views.upcoming_event_detail._fetch_leagues", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail._fetch_sports", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail.AggrigatorClient")
    def test_layout_tabs_hero_and_rail(self, MockClient, *_):
        MockClient.return_value.get_event.return_value = AGG_EVENT_RICH
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        # Two-column layout.
        self.assertContains(resp, "page-layout__main")
        self.assertContains(resp, "page-layout__rail")
        # CSS-only tabs with all three panes.
        self.assertContains(resp, 'class="seg-tabs"')
        self.assertContains(resp, 'id="pane-a"')
        self.assertContains(resp, 'id="pane-b"')
        self.assertContains(resp, 'id="pane-c"')
        # Hero countdown carries the ISO start time for the JS to read.
        self.assertContains(resp, "data-countdown-to=")
        self.assertContains(resp, "2030-01-01")
        # Win-prob bars render (model_prob present). Assert on the caption
        # text — the class names also appear in the inline <style>.
        self.assertContains(resp, "Model win probability")
        # Rail: Event Info (league) + Challenge CTA → duels hub.
        self.assertContains(resp, "NBA")
        self.assertContains(resp, reverse("core-portal:portal-duels"))
        # Countdown JS is wired for an upcoming event.
        self.assertContains(resp, "js/pages/event-countdown.js")

    @mock.patch("core.portal.services.aggrigator_client.event_live_odds", return_value=None)
    @mock.patch("core.portal.services.aggrigator_client.event_probabilities", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_historical_stats", return_value={})
    @mock.patch("core.portal.services.aggrigator_client.event_context", return_value={})
    @mock.patch("core.event.views.upcoming_event_detail._fetch_leagues", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail._fetch_sports", return_value=[])
    @mock.patch("core.event.views.upcoming_event_detail.AggrigatorClient")
    def test_empty_event_hides_winprob_and_extra_tabs(self, MockClient, *_):
        # Finalized, no markets, no model, no analytics → no win-prob bars,
        # no countdown, Odds/Analytics tabs absent; rail still present.
        MockClient.return_value.get_event.return_value = {
            **AGG_EVENT, "is_finalized": True, "markets": [],
        }
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        # Markup-only strings (class names also appear in the inline <style>).
        self.assertNotContains(resp, "Model win probability")
        self.assertNotContains(resp, "data-countdown-to=")
        self.assertNotContains(resp, 'id="pane-b"')
        self.assertNotContains(resp, 'id="pane-c"')
        # Rail Challenge CTA still renders.
        self.assertContains(resp, reverse("core-portal:portal-duels"))
        # Countdown JS is not loaded for a finalized event.
        self.assertNotContains(resp, "js/pages/event-countdown.js")
