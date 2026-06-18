"""potd_card_context: crowd split + threshold + the viewer's side share."""
from __future__ import annotations

from django.test import TestCase

from core.match.tests.factories import make_user
from core.potd.models import DailyPick
from core.potd.views import CROWD_THRESHOLD, potd_card_context

# Reuse the POTD factory from the main suite.
from core.potd.tests.test_potd import make_potd


class CrowdContextTests(TestCase):
    def test_crowd_split_counts_pct_and_threshold(self):
        potd, home, away = make_potd()
        for i in range(7):
            DailyPick.objects.create(user=make_user(f"h{i}"), potd=potd, selection=home)
        for i in range(4):
            DailyPick.objects.create(user=make_user(f"a{i}"), potd=potd, selection=away)

        crowd = potd_card_context(make_user("viewer"))["crowd"]
        self.assertEqual(crowd["total"], 11)
        self.assertTrue(crowd["threshold_met"])
        by_id = {s["selection_id"]: s for s in crowd["sides"]}
        self.assertEqual(by_id[home.id]["count"], 7)
        self.assertEqual(by_id[home.id]["pct"], 64)   # round(700/11)
        self.assertEqual(by_id[away.id]["count"], 4)
        self.assertEqual(by_id[away.id]["pct"], 36)   # round(400/11)

    def test_below_threshold_not_met(self):
        potd, home, away = make_potd()
        DailyPick.objects.create(user=make_user("h0"), potd=potd, selection=home)
        crowd = potd_card_context(make_user("viewer"))["crowd"]
        self.assertEqual(crowd["total"], 1)
        self.assertFalse(crowd["threshold_met"])
        self.assertLess(1, CROWD_THRESHOLD)

    def test_user_side_pct_reflects_viewers_pick(self):
        potd, home, away = make_potd()
        viewer = make_user("viewer")
        for i in range(10):
            DailyPick.objects.create(user=make_user(f"h{i}"), potd=potd, selection=home)
        DailyPick.objects.create(user=viewer, potd=potd, selection=away)

        crowd = potd_card_context(viewer)["crowd"]
        self.assertEqual(crowd["total"], 11)
        self.assertEqual(crowd["user_side_pct"], 9)   # round(100/11)

    def test_no_potd_returns_minimal_context(self):
        # Sanity: the early-return branch is unchanged (no POTD today).
        ctx = potd_card_context(make_user("viewer"))
        self.assertIn("potd", ctx)
