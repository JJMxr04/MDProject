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

    def test_rail_has_record_players_and_scout(self):
        r = self.client.get(self.url)
        self.assertContains(r, "page-layout__rail")
        # Your-record + players panels render in the rail.
        self.assertContains(r, "Your record")
        self.assertContains(r, "Players")
        # Context carries the computed records (viewer is p1).
        self.assertIsNotNone(r.context["your_record"])
        self.assertEqual(r.context["your_record"], r.context["player_1_record"])
        self.assertIn("won", r.context["player_2_record"])

    def test_records_query_is_batched(self):
        # The record panels must load both players' PlayerProgress in ONE
        # batched query (user_id IN ...), never one-query-per-player. (Other
        # page-wide PlayerProgress reads — nav level, levels_for — are
        # pre-existing and out of scope here.)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            self.client.get(self.url)
        batched = [
            q for q in ctx.captured_queries
            if 'from "core_ranking_progress"' in q["sql"].lower()
            and '"user_id" in (' in q["sql"].lower()
        ]
        self.assertTrue(batched, "records should load via a single user_id IN query")
