"""Backfill enqueues fetches for teams without an ok logo, per league."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.event.models import League, Sport, Team, TeamLogo
from core.event.tasks import logos


class BackfillTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        self.league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        for tid in ("38", "39"):
            Team.objects.create(
                id=f"usa-nba:{tid}", league=self.league, team_id=tid,
                sport=sport, name_long=f"Team {tid}",
            )
        # 39 already has an ok logo -> must be skipped.
        TeamLogo.objects.create(
            team_id="usa-nba:39", image=b"X", content_type="image/png",
            byte_size=1, etag="e", status="ok",
        )

    def test_enqueues_only_missing(self):
        with mock.patch.object(logos, "fetch_team_logo_task") as task:
            count = logos.run_backfill_team_logos()
        # Enqueues are paced: task.configure(schedule_in=...).defer(...).
        deferred = task.configure.return_value.defer
        deferred.assert_called_once_with(team_id="usa-nba:38")
        self.assertEqual(count, 1)

    def test_reenqueues_missing_status_row(self):
        # A team with a 'missing' logo row should still be re-enqueued.
        Team.objects.create(
            id="usa-nba:40", league=self.league, team_id="40",
            sport=self.league.sport, name_long="Team 40",
        )
        TeamLogo.objects.create(team_id="usa-nba:40", status="missing")
        with mock.patch.object(logos, "fetch_team_logo_task") as task:
            logos.run_backfill_team_logos()
        deferred = task.configure.return_value.defer
        called_ids = {c.kwargs["team_id"] for c in deferred.call_args_list}
        assert "usa-nba:40" in called_ids   # missing row -> re-enqueued
        assert "usa-nba:39" not in called_ids  # ok row -> skipped

    def test_enqueue_is_paced_with_increasing_schedule(self):
        # Enough missing teams to span several rate buckets.
        for tid in range(100, 100 + logos.BACKFILL_ENQUEUE_RATE_PER_SEC * 3):
            Team.objects.create(
                id=f"usa-nba:{tid}", league=self.league, team_id=str(tid),
                sport=self.league.sport, name_long=f"Team {tid}",
            )
        with mock.patch.object(logos, "fetch_team_logo_task") as task:
            logos.run_backfill_team_logos()
        delays = [
            c.kwargs["schedule_in"]["seconds"]
            for c in task.configure.call_args_list
        ]
        # Monotonic (paced over time), and not all zero (actually staggered).
        self.assertEqual(delays, sorted(delays))
        self.assertGreater(max(delays), 0)
        # At most RATE_PER_SEC jobs share any one-second start bucket.
        from collections import Counter
        self.assertLessEqual(
            max(Counter(delays).values()), logos.BACKFILL_ENQUEUE_RATE_PER_SEC
        )
