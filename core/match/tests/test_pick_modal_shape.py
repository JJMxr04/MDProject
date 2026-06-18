"""_shape_for_popup rewrites logos to the proxy + adds matchup tints."""
from django.test import SimpleTestCase
from django.urls import reverse

from core.match.views.available_events import _shape_for_popup


class ShapeForPopupTests(SimpleTestCase):
    def test_rewrites_logos_to_proxy_and_adds_tints(self):
        item = {
            "id": "evt-9",
            "home_team": {"name": "Mavs", "logo_url": "/v1/teams/h/logo",
                          "primary_color": "#1E40AF"},
            "away_team": {"name": "Celtics", "logo_url": "/v1/teams/a/logo",
                          "primary_color": "#DC2626"},
        }
        out = _shape_for_popup(item)
        self.assertEqual(out["event_id"], "evt-9")
        self.assertEqual(
            out["home_team"]["logo_url"],
            reverse("team-logo", kwargs={"team_id": "h"}),
        )
        self.assertEqual(
            out["away_team"]["logo_url"],
            reverse("team-logo", kwargs={"team_id": "a"}),
        )
        self.assertEqual(out["home_tint"], "#1E40AF")
        self.assertEqual(out["away_tint"], "#DC2626")

    def test_clashing_colors_drop_tints(self):
        item = {
            "id": "e",
            "home_team": {"name": "A", "primary_color": "#1E40AF"},
            "away_team": {"name": "B", "primary_color": "#1E40B2"},
        }
        out = _shape_for_popup(item)
        self.assertIsNone(out["home_tint"])
        self.assertIsNone(out["away_tint"])

    def test_missing_teams_safe(self):
        out = _shape_for_popup({"id": "e"})
        self.assertEqual(out["event_id"], "e")
        self.assertIsNone(out["home_tint"])
        self.assertIsNone(out["away_tint"])

    def test_does_not_mutate_source_cached_dict(self):
        # The input comes from the shared events cache — _shape_for_popup must
        # copy the team dicts, not edit them in place (else absolutizing the
        # logo_url would corrupt the cached aggregator body).
        item = {
            "id": "evt-9",
            "home_team": {"name": "Mavs", "logo_url": "/v1/teams/h/logo"},
            "away_team": {"name": "Celtics", "logo_url": "/v1/teams/a/logo"},
        }
        out = _shape_for_popup(item)
        self.assertEqual(item["home_team"]["logo_url"], "/v1/teams/h/logo")
        self.assertEqual(item["away_team"]["logo_url"], "/v1/teams/a/logo")
        self.assertIsNot(out["home_team"], item["home_team"])
        self.assertIsNot(out["away_team"], item["away_team"])
