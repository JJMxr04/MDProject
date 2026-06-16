"""fetch_team_logo get-or-create against a mocked aggregator client."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.event.models import League, Sport, Team, TeamLogo
from core.event.tasks import logos


class FetchTeamLogoTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )

    def test_stores_bytes(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes",
            return_value=(b"PNGDATA", "image/png", '"abc"'),
        ):
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "ok")
        row = TeamLogo.objects.get(pk="usa-nba:38")
        self.assertEqual(bytes(row.image), b"PNGDATA")
        self.assertEqual(row.etag, "abc")

    def test_negative_caches_404(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes", return_value=None
        ):
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "missing")
        self.assertEqual(TeamLogo.objects.get(pk="usa-nba:38").status, "missing")

    def test_idempotent_ok(self):
        TeamLogo.objects.create(
            team_id="usa-nba:38", image=b"X", content_type="image/png",
            byte_size=1, etag="e", status="ok",
        )
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes"
        ) as fetch:
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "ok")
        fetch.assert_not_called()

    def test_team_not_found(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes"
        ) as fetch:
            status = logos.fetch_team_logo("usa-nba:999")
        self.assertEqual(status, "team_not_found")
        fetch.assert_not_called()
