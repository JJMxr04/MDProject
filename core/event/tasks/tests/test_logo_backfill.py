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
        task.defer.assert_called_once_with(team_id="usa-nba:38")
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
        called_ids = {c.kwargs["team_id"] for c in task.defer.call_args_list}
        assert "usa-nba:40" in called_ids   # missing row -> re-enqueued
        assert "usa-nba:39" not in called_ids  # ok row -> skipped
