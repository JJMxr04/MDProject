"""Team.logo_url returns the MDProject serve URL when an ok logo exists."""

from __future__ import annotations

from django.test import TestCase

from core.event.models import League, Sport, Team, TeamLogo


class TeamLogoUrlTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        self.team = Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )

    def test_none_when_no_logo(self):
        self.assertIsNone(self.team.logo_url)

    def test_url_when_ok_logo(self):
        TeamLogo.objects.create(
            team=self.team, image=b"X", content_type="image/png",
            byte_size=1, etag="e", status="ok",
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.logo_url, "/logos/teams/usa-nba:38")

    def test_none_when_missing_status(self):
        TeamLogo.objects.create(team=self.team, status="missing")
        self.team.refresh_from_db()
        self.assertIsNone(self.team.logo_url)
