"""Render-level tests for the _event_matchup tint custom-property."""
from django.template import Context, Template
from django.test import SimpleTestCase

TPL = Template('{% include "portal/components/_event_matchup.html" %}')


def _fixture(home_tint=None, away_tint=None):
    return {
        "status": "upcoming",
        "league_name": "NBA",
        "start_time": None,
        "home": {"name": "Mavs", "logo_url": "", "score": None, "tint": home_tint},
        "away": {"name": "Celtics", "logo_url": "", "score": None, "tint": away_tint},
        "winner_label": None,
    }


class EventMatchupTintTests(SimpleTestCase):
    def test_emits_team_tint_var_when_set(self):
        html = TPL.render(Context({"fixture": _fixture("#1E40AF", "#DC2626")}))
        self.assertIn("--team-tint: #1E40AF;", html)
        self.assertIn("--team-tint: #DC2626;", html)

    def test_omits_team_tint_var_when_none(self):
        html = TPL.render(Context({"fixture": _fixture(None, None)}))
        self.assertNotIn("--team-tint", html)
        # Sanity: the partial still renders the matchup body.
        self.assertIn("matchup__team--home", html)


class EventMatchupStatusTests(SimpleTestCase):
    def _fx(self, status, home_score=None, away_score=None):
        fx = _fixture()
        fx["status"] = status
        fx["home"]["score"] = home_score
        fx["away"]["score"] = away_score
        return fx

    def test_live_renders_running_score(self):
        html = TPL.render(Context({"fixture": self._fx("live", 54, 49)}))
        self.assertIn("matchup__score", html)
        self.assertIn(">54<", html)
        self.assertIn(">49<", html)
        self.assertIn("LIVE", html)

    def test_postponed_renders_badge_not_vs(self):
        html = TPL.render(Context({"fixture": self._fx("postponed")}))
        self.assertIn("matchup__status", html)
        self.assertIn("Postponed", html)
        self.assertNotIn(">VS<", html)

    def test_canceled_renders_badge(self):
        html = TPL.render(Context({"fixture": self._fx("canceled")}))
        self.assertIn("matchup__status", html)
        self.assertIn("Canceled", html)
