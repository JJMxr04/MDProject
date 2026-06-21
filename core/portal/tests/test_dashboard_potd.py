"""Dashboard surfaces the POTD hype card (top of feed) and no longer the
small hero widget."""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.match.tests.factories import make_user
from core.potd.tests.test_potd import make_potd


class DashboardPotdHypeTests(TestCase):
    def setUp(self):
        self.user = make_user("dash")
        self.client.force_login(self.user)

    def test_dashboard_renders_hype_card_not_hero_widget(self):
        make_potd()
        resp = self.client.get(reverse("core-portal:portal-dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "potd-hype")
        self.assertContains(resp, 'data-action="potd-pick"')
        # The old buried hero widget is gone.
        self.assertNotContains(resp, "turn-hero__potd")

    def test_dashboard_without_potd_shows_next_pick_countdown(self):
        # No POTD today → the empty-state card still renders with a countdown
        # to the next pick, but no pickable selections.
        resp = self.client.get(reverse("core-portal:portal-dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "potd-hype--empty")
        self.assertContains(resp, "data-countdown-to")
        self.assertNotContains(resp, 'data-action="potd-pick"')
