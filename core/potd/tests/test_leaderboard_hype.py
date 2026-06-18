"""The Pick of the Day page pins the hype card at the top (replacing the
thin 'Today:' strip)."""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.match.tests.factories import make_user
from core.potd.tests.test_potd import make_potd


class LeaderboardHypeTests(TestCase):
    def setUp(self):
        self.user = make_user("lb")
        self.client.force_login(self.user)

    def test_hype_card_pinned_top_and_old_strip_gone(self):
        make_potd()
        resp = self.client.get(reverse("core-portal:potd-leaderboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "potd-hype")
        self.assertContains(resp, 'data-action="potd-pick"')
        # The old thin "Today:" strip is replaced.
        self.assertNotContains(resp, "potd-today-link")
