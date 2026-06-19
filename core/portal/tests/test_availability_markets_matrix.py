"""Markets section of /web/portal/availability/ renders a per-sport spreadsheet
(leagues x humanized markets, real per-league coverage). The aggregator client is
patched so tests stay hermetic; the page caches via _load_catalog so each test
clears the cache first."""
from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core.event.providers.aggregator_client import AggrigatorError
from core.match.tests.factories import make_user

CLIENT = "core.portal.views.availability.AggrigatorClient"

_DEFAULT_MARKETS = {
    "FOOTBALL": ["NFL_POINTS_ML", "NFL_POINTS_OU", "NFL_PASSING_YARDS_OU", "NCAAF_POINTS_OU"],
    "SOCCER": ["EPL_GOALS_ML3WAY", "EPL_BTTS", "BRASILEIRAO_SERIE_B_GOALS_OU"],
}


def _fake_client(**overrides):
    client = mock.Mock()
    client.get_sports.return_value = overrides.get(
        "sports",
        [{"id": "FOOTBALL", "name": "Football"}, {"id": "SOCCER", "name": "Soccer"}],
    )
    client.get_leagues.return_value = overrides.get(
        "leagues",
        [
            {"id": "NFL", "name": "NFL", "sport_id": "FOOTBALL"},
            {"id": "NCAAF", "name": "NCAA Football", "sport_id": "FOOTBALL"},
            {"id": "EPL", "name": "EPL", "sport_id": "SOCCER"},
            {"id": "BRASILEIRAO_SERIE_B", "name": "Brasileirao Serie B", "sport_id": "SOCCER"},
        ],
    )
    client.get_bookmakers.return_value = overrides.get(
        "bookmakers", [{"id": "dk", "name": "DraftKings", "active": True}]
    )
    markets_by_sport = overrides.get("markets_by_sport", _DEFAULT_MARKETS)

    def _market_types(sport_id=None):
        if sport_id is None:
            return sorted({m for ms in markets_by_sport.values() for m in ms})
        return markets_by_sport.get(sport_id, [])

    client.get_market_types.side_effect = _market_types
    return client


class AvailabilityMarketsContextTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("avail")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:portal-availability")

    def _matrix(self, **overrides):
        with mock.patch(CLIENT, return_value=_fake_client(**overrides)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        return resp.context["markets_matrix"]

    def test_blocks_in_sports_order(self):
        matrix = self._matrix()
        self.assertEqual([b["sport_name"] for b in matrix], ["Football", "Soccer"])

    def test_columns_humanized_and_ordered(self):
        matrix = self._matrix()
        football = matrix[0]
        soccer = matrix[1]
        self.assertEqual(football["columns"], ["Moneyline", "Total", "Passing Yards O/U"])
        self.assertEqual(soccer["columns"], ["Match Result (3-Way)", "Total", "Both Teams to Score"])

    def test_per_league_cells(self):
        football = self._matrix()[0]
        self.assertEqual(
            football["rows"],
            [
                {"league": "NCAA Football", "cells": [False, True, False]},
                {"league": "NFL", "cells": [True, True, True]},
            ],
        )

    def test_sport_with_no_markets_is_omitted(self):
        matrix = self._matrix(markets_by_sport={"FOOTBALL": _DEFAULT_MARKETS["FOOTBALL"], "SOCCER": []})
        self.assertEqual([b["sport_name"] for b in matrix], ["Football"])

    def test_no_markets_at_all_is_empty_matrix(self):
        matrix = self._matrix(markets_by_sport={"FOOTBALL": [], "SOCCER": []})
        self.assertEqual(matrix, [])

    def test_longest_prefix_collision_attributes_to_correct_league(self):
        # VNL_WOMEN_* must NOT be attributed to VNL (longest-prefix wins, end to end).
        matrix = self._matrix(
            sports=[{"id": "VOLLEYBALL", "name": "Volleyball"}],
            leagues=[
                {"id": "VNL", "name": "VNL", "sport_id": "VOLLEYBALL"},
                {"id": "VNL_WOMEN", "name": "VNL Women", "sport_id": "VOLLEYBALL"},
            ],
            markets_by_sport={"VOLLEYBALL": ["VNL_POINTS_OU", "VNL_WOMEN_POINTS_ML"]},
        )
        block = matrix[0]
        self.assertEqual(block["columns"], ["Moneyline", "Total"])
        self.assertEqual(
            block["rows"],
            [
                {"league": "VNL", "cells": [False, True]},
                {"league": "VNL Women", "cells": [True, False]},
            ],
        )

    def test_aggregator_unreachable_renders_empty_matrix(self):
        fake = mock.Mock()
        fake.get_sports.side_effect = AggrigatorError("boom")
        with mock.patch(CLIENT, return_value=fake):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["markets_matrix"], [])
        self.assertTrue(resp.context["aggregator_unreachable"])


class AvailabilityMarketsRenderTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("availr")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:portal-availability")

    def _get(self, **overrides):
        with mock.patch(CLIENT, return_value=_fake_client(**overrides)):
            return self.client.get(self.url)

    def test_renders_one_matrix_table_per_sport(self):
        resp = self._get()
        html = resp.content.decode()
        self.assertEqual(html.count('class="avail-table avail-table--matrix avail-matrix"'), 2)
        # Sport headings + humanized columns + league names present.
        for needle in [
            "Football", "Soccer",
            "Moneyline", "Total", "Passing Yards O/U",
            "Match Result (3-Way)", "Both Teams to Score",
            "NFL", "NCAA Football", "EPL", "Brasileirao Serie B",
        ]:
            self.assertContains(resp, needle)
        # Raw league-prefixed type strings must NOT leak into the page.
        self.assertNotContains(resp, "NFL_POINTS_ML")
        self.assertNotContains(resp, "_GOALS_")

    def test_check_and_dash_cells(self):
        resp = self._get()
        html = resp.content.decode()
        cell = '<span class="avail-pill avail-pill--ok"><i class="bi bi-check-lg"></i></span>'
        # True cells: football NFL(3)+NCAAF(1)=4, soccer EPL(2)+Brasileirao(1)=3 -> 7.
        self.assertEqual(html.count(cell), 7)
        # At least one empty cell rendered as an em dash.
        self.assertIn("avail-matrix__no", html)

    def test_no_markets_at_all_shows_empty_state(self):
        resp = self._get(markets_by_sport={"FOOTBALL": [], "SOCCER": []})
        self.assertContains(resp, "No markets available.")
