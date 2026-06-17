"""Match-detail is on the shared .page-layout and drops the stale CSS link."""
from django.test import TestCase
from django.urls import reverse

from core.match.tests.factories import make_match, make_user


class MatchDetailMobileTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.client.force_login(self.p1)
        self.url = reverse("core-portal:portal-my-match-detail", args=[self.match.id])

    def test_renders_within_page_layout(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "page-layout")

    def test_drops_stale_css_link(self):
        r = self.client.get(self.url)
        self.assertNotContains(r, "my_match_detail.css")
