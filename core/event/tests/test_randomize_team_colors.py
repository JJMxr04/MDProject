"""Tests for the randomize_team_colors dev management command."""
import re

from django.core.management import call_command
from django.test import TestCase

from core.event.models import Team
from core.match.tests.factories import make_league, make_team

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class RandomizeTeamColorsCommandTests(TestCase):
    def setUp(self):
        self.league = make_league("NFL")
        # Two teams with null colors, one already coloured.
        self.t_null_a = make_team(self.league, "A_TEAM")
        self.t_null_b = make_team(self.league, "B_TEAM")
        self.t_set = make_team(self.league, "C_TEAM")
        self.t_set.primary_color = "#abcdef"
        self.t_set.save(update_fields=["primary_color"])

    def test_fills_only_nulls_by_default(self):
        call_command("randomize_team_colors")
        for t in (self.t_null_a, self.t_null_b):
            t.refresh_from_db()
            self.assertIsNotNone(t.primary_color)
            self.assertRegex(t.primary_color, HEX_RE)
            for fld in ("secondary_color", "primary_contrast", "secondary_contrast"):
                self.assertRegex(getattr(t, fld), HEX_RE)
        # The already-coloured team is untouched without --overwrite.
        self.t_set.refresh_from_db()
        self.assertEqual(self.t_set.primary_color, "#abcdef")

    def test_overwrite_redoes_all(self):
        call_command("randomize_team_colors", "--overwrite")
        self.t_set.refresh_from_db()
        self.assertNotEqual(self.t_set.primary_color, "#abcdef")
        self.assertRegex(self.t_set.primary_color, HEX_RE)
