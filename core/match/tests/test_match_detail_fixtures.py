"""Match-detail view: per-game fixtures (MDProject logos) + player hero.

Each game card renders the shared ``_event_matchup.html`` fed by a
``fixture_from_event`` attached on the view, so team crests resolve to
MDProject's own ``/logos/teams/{id}`` mirror (not an aggregator URL). The
header is the shared ``_player_vs.html`` hero showing both players.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.event.models.team_logo import TeamLogo
from core.game.models import Game
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_selection,
    make_team,
    make_two_way_market,
    make_user,
)


class MatchDetailFixtureTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)

        league = make_league()
        home = make_team(league, "HOME_FX")
        away = make_team(league, "AWAY_FX")
        # ``status="ok"`` makes Team.logo_url resolve to the /logos/teams route.
        TeamLogo.objects.create(team=home, status="ok", byte_size=1)
        TeamLogo.objects.create(team=away, status="ok", byte_size=1)

        event = make_event(
            league, home=home, away=away,
            start_time=timezone.now() + timedelta(days=2),
        )
        _, home_sel, _ = make_two_way_market(event)
        # Picks the event into one of p1's regular slots.
        Game.objects.upload_pick(
            current_user=self.p1, match=self.match,
            event_id=event.id, selection_id=home_sel.id,
        )

    def _get(self):
        self.client.force_login(self.p1)
        return self.client.get(
            reverse("core-portal:portal-my-match-detail", args=[self.match.id])
        )

    def test_each_game_has_mdproject_fixture(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        games = list(resp.context["player_1_games"]) + (
            [resp.context["golden_game"]] if resp.context["golden_game"] else []
        )
        self.assertTrue(games)
        # The game holding the picked event carries a fixture with MDProject
        # mirror logo URLs.
        picked = [g for g in games if g.event and g.event.home_team_id]
        self.assertTrue(picked)
        fx = picked[0].fixture
        self.assertIsNotNone(fx)
        self.assertIn("/logos/teams/", fx["home"]["logo_url"])

    def test_game_card_renders_mdproject_logo_img(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        # The rendered page carries a team-logo <img> pointing at the local
        # mirror route, proving the shared matchup partial is wired up.
        self.assertContains(resp, 'src="/logos/teams/')

    def test_pick_modal_uses_modal_ui_shell(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        # The pick modal migrated off Bootstrap's .modal fade to the portal
        # modal-ui shell (shell.js toggles .is-open).
        self.assertContains(resp, '<div class="modal-ui" id="pickModal"')
        self.assertNotContains(resp, '<div class="modal fade" id="pickModal"')

    def test_player_hero_renders_both_users(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.p1.username)
        self.assertContains(resp, self.p2.username)
        self.assertContains(resp, "vs-card__side--home")
        self.assertContains(resp, "vs-card__side--away")

    def test_player_hero_carries_per_side_colors(self):
        # The hero context dicts surface each player's own home/away color:
        # the home side uses player_1's home_color, the away side uses
        # player_2's away_color. NULL → None (CSS default applies).
        self.p1.home_color = "#112233"
        self.p1.away_color = "#445566"
        self.p1.save(update_fields=["home_color", "away_color"])
        self.p2.home_color = "#778899"
        self.p2.away_color = "#AABBCC"
        self.p2.save(update_fields=["home_color", "away_color"])

        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["home_player"]["color"], "#112233")
        self.assertEqual(resp.context["away_player"]["color"], "#AABBCC")

    def test_player_hero_colors_default_to_none(self):
        # Unset colors leave the dicts' color None so the template omits the
        # inline var and the CSS blue/red default takes over.
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["home_player"]["color"])
        self.assertIsNone(resp.context["away_player"]["color"])

    def test_player_hero_handles_missing_opponent(self):
        # A match without an opponent (player_2 None) must not blow up on the
        # away color; it falls back to None.
        from core.match.tests.factories import make_match
        solo = make_match(self.p1, None, accept=False)
        self.client.force_login(self.p1)
        resp = self.client.get(
            reverse("core-portal:portal-my-match-detail", args=[solo.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["away_player"]["color"])

    def test_fixtures_do_not_nplus1_on_team_logos(self):
        # Team.logo_url reads the reverse OneToOne Team.logo (TeamLogo). The
        # games queryset must select_related it so the per-game fixtures don't
        # issue a standalone TeamLogo SELECT per team (the N+1 guarded here).
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.p1)
        url = reverse("core-portal:portal-my-match-detail", args=[self.match.id])
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        standalone = [
            q for q in ctx.captured_queries
            if 'from "core_team_logo"' in q["sql"].lower()
        ]
        self.assertEqual(
            standalone, [],
            f"N+1 on TeamLogo: {len(standalone)} standalone fetch(es); "
            "team logos should load via the games select_related JOIN.",
        )
