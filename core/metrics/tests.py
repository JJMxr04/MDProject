"""core_metrics — ProductEvent, track(), session dedupe, report command."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from core.match.tests.factories import make_user
from core.metrics.models import ProductEvent, track
from core.metrics.signals import track_session_start


class TrackTests(TestCase):
    def test_track_writes_event_with_props(self):
        user = make_user("trk")
        track(user, "pick_made", match_id="abc", golden=False)
        ev = ProductEvent.objects.get(user=user, name="pick_made")
        self.assertEqual(ev.props, {"match_id": "abc", "golden": False})

    def test_track_accepts_none_user(self):
        track(None, "match_completed", match_id="abc")
        self.assertTrue(
            ProductEvent.objects.filter(user=None, name="match_completed").exists()
        )

    def test_track_never_raises(self):
        # name longer than max_length would raise on strict backends —
        # must be swallowed, not propagated.
        track(make_user("boom"), "x" * 500)


class SessionStartDedupeTests(TestCase):
    def test_one_session_start_per_day(self):
        user = make_user("sess")
        track_session_start(sender=None, request=None, user=user)
        track_session_start(sender=None, request=None, user=user)
        self.assertEqual(
            ProductEvent.objects.filter(user=user, name="session_start").count(), 1,
        )

    def test_login_fires_session_start(self):
        user = make_user("login")
        self.client.force_login(user)
        self.assertEqual(
            ProductEvent.objects.filter(user=user, name="session_start").count(), 1,
        )


class MetricsReportCommandTests(TestCase):
    def test_report_runs_and_prints_sections(self):
        user = make_user("rep")
        track(user, "session_start")
        track(user, "pick_made", match_id="m1")
        out = StringIO()
        call_command("metrics_report", "--days", "7", stdout=out)
        text = out.getvalue()
        self.assertIn("D1/D7 retention", text)
        self.assertIn("Picks per user", text)
        self.assertIn("Both-players-return", text)
        self.assertIn("weekly_active_users=1", text)
