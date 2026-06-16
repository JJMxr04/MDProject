"""Render tests for the portal card partials."""
from __future__ import annotations

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TeamLogoPartialTests(SimpleTestCase):
    TPL = "portal/components/_team_logo.html"

    def test_renders_img_when_logo_present(self):
        html = render_to_string(self.TPL, {"team": {"name": "Mavericks", "logo_url": "/m.png"}})
        self.assertIn('<img', html)
        self.assertIn('/m.png', html)

    def test_renders_initials_when_logo_absent(self):
        html = render_to_string(self.TPL, {"team": {"name": "Mavericks", "logo_url": ""}})
        self.assertNotIn('<img', html)
        self.assertIn('MA', html)  # first two letters, upper-cased


class EventMatchupPartialTests(SimpleTestCase):
    TPL = "portal/components/_event_matchup.html"

    def _fx(self, **over):
        fx = {
            "league_name": "NBA",
            "start_time": None,
            "status": "upcoming",
            "home": {"name": "Mavericks", "logo_url": "", "score": None},
            "away": {"name": "Celtics", "logo_url": "", "score": None},
            "winner_label": None,
        }
        fx.update(over)
        return fx

    def test_upcoming_shows_vs_no_score_no_winner(self):
        html = render_to_string(self.TPL, {"fixture": self._fx()})
        self.assertIn("NBA", html)
        self.assertIn("Mavericks", html)
        self.assertIn("Celtics", html)
        self.assertIn("VS", html)
        self.assertNotIn("won", html.lower())

    def test_final_shows_score_and_winner(self):
        fx = self._fx(
            status="final", winner_label="Mavericks",
            home={"name": "Mavericks", "logo_url": "", "score": 112},
            away={"name": "Celtics", "logo_url": "", "score": 108},
        )
        html = render_to_string(self.TPL, {"fixture": fx})
        self.assertIn("112", html)
        self.assertIn("108", html)
        self.assertIn("Mavericks won", html)

    def test_live_shows_live_chip(self):
        html = render_to_string(self.TPL, {"fixture": self._fx(status="live")})
        self.assertIn("LIVE", html)

    def test_no_fixture_renders_nothing(self):
        html = render_to_string(self.TPL, {"fixture": None})
        self.assertEqual(html.strip(), "")


class RailPanelPartialTests(SimpleTestCase):
    TPL = "portal/components/_rail_panel.html"

    def test_renders_title_and_body(self):
        html = render_to_string(self.TPL, {"title": "Duel Stats", "body_html": "<b>hi</b>"})
        self.assertIn("Duel Stats", html)
        self.assertIn("<b>hi</b>", html)


class EventFixtureFilterTests(SimpleTestCase):
    def test_filter_normalizes_dict(self):
        from core.event.templatetags.event_cards import event_fixture
        fx = event_fixture({"home_team": {"name": "A"}, "away_team": {"name": "B"}})
        self.assertEqual(fx["home"]["name"], "A")
