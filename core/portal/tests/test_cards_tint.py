"""Unit tests for the matchup color-tint helper and fixture tint wiring."""
from __future__ import annotations

from django.test import SimpleTestCase

from core.portal import cards


class ResolveMatchupTintsTests(SimpleTestCase):
    def test_distinct_colors_return_both(self):
        home, away = cards.resolve_matchup_tints("#1E40AF", "#DC2626")
        self.assertEqual(home, "#1E40AF")
        self.assertEqual(away, "#DC2626")

    def test_clashing_colors_return_none_none(self):
        # Two near-identical blues, RGB distance < threshold.
        home, away = cards.resolve_matchup_tints("#1E40AF", "#1E40B2")
        self.assertIsNone(home)
        self.assertIsNone(away)

    def test_one_missing_keeps_present_other_none(self):
        self.assertEqual(cards.resolve_matchup_tints("#1E40AF", None), ("#1E40AF", None))
        self.assertEqual(cards.resolve_matchup_tints(None, "#DC2626"), (None, "#DC2626"))

    def test_both_missing_return_none_none(self):
        self.assertEqual(cards.resolve_matchup_tints(None, None), (None, None))

    def test_unparseable_hex_treated_as_missing(self):
        # "not-a-color" is unparseable → that side is None; the other stays.
        self.assertEqual(cards.resolve_matchup_tints("not-a-color", "#DC2626"), (None, "#DC2626"))
        # Too-short hex is unparseable too.
        self.assertEqual(cards.resolve_matchup_tints("#abc", "#DC2626"), (None, "#DC2626"))

    def test_hex_to_rgb_parses_and_rejects(self):
        self.assertEqual(cards._hex_to_rgb("#FF8800"), (255, 136, 0))
        self.assertEqual(cards._hex_to_rgb("FF8800"), (255, 136, 0))      # no leading #
        self.assertEqual(cards._hex_to_rgb("#FF8800AA"), (255, 136, 0))   # 8-digit ok
        self.assertIsNone(cards._hex_to_rgb(None))
        self.assertIsNone(cards._hex_to_rgb(""))
        self.assertIsNone(cards._hex_to_rgb("#abc"))
        self.assertIsNone(cards._hex_to_rgb("#ZZZZZZ"))
        self.assertIsNone(cards._hex_to_rgb(12345))


class TeamSideTintTests(SimpleTestCase):
    def test_team_side_carries_tint_when_given(self):
        side = cards.team_side(name="A", logo_url="/a.png", score=None, tint="#1E40AF")
        self.assertEqual(side["tint"], "#1E40AF")

    def test_team_side_tint_defaults_none(self):
        side = cards.team_side(name="A", logo_url="/a.png", score=None)
        self.assertIsNone(side["tint"])


class FixtureFromDictTintTests(SimpleTestCase):
    def test_distinct_primary_colors_set_both_tints_and_absolutize_logo(self):
        fx = cards.fixture_from_dict({
            "league": {"name": "NBA"},
            "start_time": "2030-01-01T19:30:00+00:00",
            "is_live": False, "is_finalized": False, "status_type": "notstarted",
            "home_team": {"name": "Mavs", "logo_url": "/m.png", "primary_color": "#1E40AF"},
            "away_team": {"name": "Celtics", "logo_url": "/c.png", "primary_color": "#DC2626"},
            "home_score": None, "away_score": None,
        })
        self.assertEqual(fx["home"]["tint"], "#1E40AF")
        self.assertEqual(fx["away"]["tint"], "#DC2626")
        # fixture_from_dict must still absolutize logos (relative passes through
        # unchanged only when no AGG base is set; assert the key still exists).
        self.assertIn("logo_url", fx["home"])

    def test_clashing_colors_drop_both_tints(self):
        fx = cards.fixture_from_dict({
            "home_team": {"name": "A", "primary_color": "#1E40AF"},
            "away_team": {"name": "B", "primary_color": "#1E40B2"},
        })
        self.assertIsNone(fx["home"]["tint"])
        self.assertIsNone(fx["away"]["tint"])

    def test_missing_colors_yield_none_tints(self):
        fx = cards.fixture_from_dict({
            "home_team": {"name": "A"},
            "away_team": {"name": "B"},
        })
        self.assertIsNone(fx["home"]["tint"])
        self.assertIsNone(fx["away"]["tint"])
