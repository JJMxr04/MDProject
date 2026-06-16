"""EventSerializer team brief includes logo_url from the model property."""

from __future__ import annotations

from django.test import TestCase

from core.event.models import Event, League, Sport, Team, TeamLogo
from core.event.serializers.event import EventSerializer


class EventLogoFieldTests(TestCase):
    def test_home_team_brief_has_logo_url(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        home = Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )
        TeamLogo.objects.create(
            team=home, image=b"X", content_type="image/png",
            byte_size=1, etag="e", status="ok",
        )
        event = Event.objects.create(id="evt-1", league=league, sport=sport, home_team=home)
        data = EventSerializer(event).data
        self.assertEqual(data["home_team"]["logo_url"], "/logos/teams/usa-nba:38")

    def test_logo_url_none_without_logo(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        away = Team.objects.create(
            id="usa-nba:39", league=league, team_id="39", sport=sport,
            name_long="Celtics",
        )
        event = Event.objects.create(id="evt-2", league=league, sport=sport, away_team=away)
        data = EventSerializer(event).data
        self.assertIsNone(data["away_team"]["logo_url"])
