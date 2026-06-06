"""Tiebreaker submission window — closes at Golden Game kickoff.

The tiebreaker score is a guess at the Golden Game's final total, so
submissions are rejected once that event has started (and the detail page
hides the submit button via the same ``tiebreaker_locked`` gate).
"""

import json
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
)


class TiebreakerWindowTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        league = make_league("GOLDEN")
        self.golden_event = make_event(
            league, start_time=timezone.now() + timedelta(days=2),
        )
        _, g_home, _ = make_two_way_market(self.golden_event)
        self.match = make_match(self.p1, self.p2, golden_selection=g_home)
        self.url = reverse(
            "core-portal:portal-upload-tiebreaker-score", args=[self.match.id],
        )

    def _post_score(self, user, score):
        self.client.force_login(user)
        return self.client.post(
            self.url,
            data=json.dumps({"tiebreaker_score": score}),
            content_type="application/json",
        )

    def _start_golden_event(self):
        self.golden_event.start_time = timezone.now() - timedelta(minutes=5)
        self.golden_event.save(update_fields=["start_time"])

    def test_submission_before_kickoff_accepted(self):
        r = self._post_score(self.p1, 40)
        self.assertEqual(r.status_code, 200)
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 40)

    def test_player_2_submission_writes_player_2_total(self):
        r = self._post_score(self.p2, 33)
        self.assertEqual(r.status_code, 200)
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.player_2_total, 33)
        self.assertEqual(tb.owner_total, 0)

    def test_submission_after_kickoff_rejected(self):
        self._start_golden_event()
        r = self._post_score(self.p1, 40)
        self.assertEqual(r.status_code, 403)
        self.assertIn("already started", r.json()["message"])
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.owner_total, 0)

    def test_rejection_applies_to_both_players(self):
        self._start_golden_event()
        r = self._post_score(self.p2, 21)
        self.assertEqual(r.status_code, 403)
        tb = self.match.tiebreaker
        tb.refresh_from_db()
        self.assertEqual(tb.player_2_total, 0)

    def test_detail_page_hides_submit_button_after_kickoff(self):
        self._start_golden_event()
        self.client.force_login(self.p1)
        detail_url = reverse("core-portal:portal-my-match-detail", args=[self.match.id])
        r = self.client.get(detail_url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Submit Your Tiebreaker Score")
        self.assertContains(r, "Tiebreaker submissions are closed")

    def test_detail_page_shows_golden_locked_market(self):
        """The golden card must surface which market the system locked —
        users were checking the DB to find it."""
        self.client.force_login(self.p1)
        detail_url = reverse("core-portal:portal-my-match-detail", args=[self.match.id])
        r = self.client.get(detail_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Market: Moneyline")
