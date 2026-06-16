"""Tests for logo rendering in the upcoming-event detail view.

Verifies that _TeamAdapter exposes logo_url as a plain string (matching
the _team_logo.html partial contract) and that the partial renders an
<img> when a URL is present and initials when it is absent.
"""
from __future__ import annotations

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.event.views.upcoming_event_detail import _TeamAdapter


class TeamAdapterLogoUrlTests(SimpleTestCase):
    def test_logo_url_is_plain_string_when_present(self):
        adapter = _TeamAdapter({"name_long": "Arsenal", "logo_url": "https://cdn.example.com/a.png"})
        self.assertIsInstance(adapter.logo_url, str)
        self.assertEqual(adapter.logo_url, "https://cdn.example.com/a.png")

    def test_logo_url_is_none_when_absent(self):
        adapter = _TeamAdapter({"name_long": "Arsenal"})
        self.assertIsNone(adapter.logo_url)

    def test_logo_url_is_none_when_empty_string(self):
        adapter = _TeamAdapter({"name_long": "Arsenal", "logo_url": ""})
        self.assertIsNone(adapter.logo_url)

    def test_none_team_produces_none_logo_url(self):
        adapter = _TeamAdapter(None)
        self.assertIsNone(adapter.logo_url)


LOGO_PARTIAL = "portal/components/_team_logo.html"


class TeamAdapterPartialRenderTests(SimpleTestCase):
    """Prove the adapter works with the shared partial end-to-end."""

    def test_renders_img_when_logo_present(self):
        adapter = _TeamAdapter({"name_long": "Arsenal", "logo_url": "https://cdn.example.com/a.png"})
        html = render_to_string(LOGO_PARTIAL, {"team": adapter, "size": 96})
        self.assertIn("<img", html)
        self.assertIn("https://cdn.example.com/a.png", html)
        self.assertIn('alt="Arsenal"', html)

    def test_renders_initials_when_logo_absent(self):
        adapter = _TeamAdapter({"name_long": "Arsenal"})
        html = render_to_string(LOGO_PARTIAL, {"team": adapter, "size": 96})
        self.assertNotIn("<img", html)
        self.assertIn("AR", html)

    def test_renders_initials_when_logo_empty_string(self):
        adapter = _TeamAdapter({"name_long": "Chelsea", "logo_url": ""})
        html = render_to_string(LOGO_PARTIAL, {"team": adapter, "size": 96})
        self.assertNotIn("<img", html)
        self.assertIn("CH", html)
