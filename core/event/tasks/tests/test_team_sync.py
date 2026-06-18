"""run_sync_team_data overwrites the 8 syncable fields on existing teams only."""

from unittest.mock import patch

from django.test import TestCase

from core.event.models import League, Sport, Team
from core.event.tasks.team_sync import run_sync_team_data


class RunSyncTeamDataTests(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(id="FOOTBALL", name="Football")
        self.league = League.objects.create(id="NFL", name="NFL", sport=self.sport)
        self.dal = Team.objects.create(
            id="NFL:DAL", league=self.league, team_id="DAL", sport=self.sport,
            name_long="Old Dallas", name_medium="OldD", name_short="OD",
            primary_color="#111111", secondary_color="#222222",
            primary_contrast="#333333", secondary_contrast="#444444",
            stat_entity_id="old",
        )
        self.original_public_id = self.dal.public_id

    def _page(self):
        return {
            "items": [
                {
                    "id": "NFL:DAL", "league_id": "NFL", "team_id": "DAL",
                    "sport_id": "FOOTBALL",
                    "name_long": "Dallas Cowboys", "name_medium": "Cowboys",
                    "name_short": "DAL",
                    "primary_color": "#003594",
                    "secondary_color": None,
                    "primary_contrast": "#FFFFFF",
                    "secondary_contrast": "#869397",
                    "stat_entity_id": "home",
                },
                {
                    "id": "NFL:GHOST", "league_id": "NFL", "team_id": "GHOST",
                    "sport_id": "FOOTBALL", "name_long": "Ghost",
                    "name_medium": "Ghost", "name_short": "GHO",
                    "primary_color": "#000000", "secondary_color": "#000000",
                    "primary_contrast": "#000000", "secondary_contrast": "#000000",
                    "stat_entity_id": "x",
                },
            ],
            "page": 1, "page_size": 200, "pages": 1, "total": 2,
        }

    @patch("core.event.tasks.team_sync.AggrigatorClient.list_teams", autospec=True)
    def test_overwrites_known_skips_unknown(self, mock_list_teams):
        mock_list_teams.return_value = self._page()
        updated = run_sync_team_data()

        self.assertEqual(updated, 1)
        self.dal.refresh_from_db()
        self.assertEqual(self.dal.name_long, "Dallas Cowboys")
        self.assertEqual(self.dal.name_medium, "Cowboys")
        self.assertEqual(self.dal.name_short, "DAL")
        self.assertEqual(self.dal.primary_color, "#003594")
        self.assertIsNone(self.dal.secondary_color)
        self.assertEqual(self.dal.primary_contrast, "#FFFFFF")
        self.assertEqual(self.dal.secondary_contrast, "#869397")
        self.assertEqual(self.dal.stat_entity_id, "home")
        self.assertEqual(self.dal.public_id, self.original_public_id)
        self.assertEqual(self.dal.league_id, "NFL")
        self.assertEqual(self.dal.sport_id, "FOOTBALL")
        self.assertEqual(self.dal.team_id, "DAL")
        self.assertFalse(Team.objects.filter(id="NFL:GHOST").exists())

    @patch("core.event.tasks.team_sync.AggrigatorClient.list_teams", autospec=True)
    def test_pages_through_all_pages(self, mock_list_teams):
        def _side_effect(self_client, page=1, page_size=200, league_id=None):
            if page == 1:
                return {"items": [self._page()["items"][0]], "pages": 2}
            return {"items": [], "pages": 2}
        mock_list_teams.side_effect = _side_effect
        updated = run_sync_team_data()
        self.assertEqual(updated, 1)
        self.assertEqual(mock_list_teams.call_count, 2)
