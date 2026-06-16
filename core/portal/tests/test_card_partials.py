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
