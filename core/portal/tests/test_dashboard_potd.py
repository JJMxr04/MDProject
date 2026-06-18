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

    def test_dashboard_without_potd_is_fine(self):
        # No POTD today → partial renders nothing, page still 200.
        resp = self.client.get(reverse("core-portal:portal-dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "potd-hype")
