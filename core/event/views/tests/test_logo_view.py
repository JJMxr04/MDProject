"""GET /logos/teams/{id}: hit, 304, 404."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.event.models import League, Sport, Team, TeamLogo


class LogoViewTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        self.team = Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )

    def _url(self, team_id):
        return reverse("team-logo", kwargs={"team_id": team_id})

    def test_hit(self):
        TeamLogo.objects.create(
            team=self.team, image=b"PNGDATA", content_type="image/png",
            byte_size=7, etag="abc123", status="ok",
        )
        resp = self.client.get(self._url("usa-nba:38"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertEqual(resp["ETag"], '"abc123"')
        self.assertEqual(bytes(resp.content), b"PNGDATA")

    def test_304(self):
        TeamLogo.objects.create(
            team=self.team, image=b"PNGDATA", content_type="image/png",
            byte_size=7, etag="abc123", status="ok",
        )
        resp = self.client.get(self._url("usa-nba:38"), HTTP_IF_NONE_MATCH='"abc123"')
        self.assertEqual(resp.status_code, 304)

    def test_404(self):
        resp = self.client.get(self._url("usa-nba:999"))
        self.assertEqual(resp.status_code, 404)
