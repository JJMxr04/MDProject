"""Unit tests for market-type label/coverage helpers (no Django needed)."""
from __future__ import annotations
import unittest

from core.event.odds.market_labels import (
    build_sport_matrix,
    column_sort_key,
    humanize_market_type,
    split_market_type,
)


class TestSplitMarketType(unittest.TestCase):
    LEAGUES = ["NFL", "NCAAF", "VNL", "VNL_WOMEN", "BRASILEIRAO_SERIE_B"]

    def test_simple_prefix(self):
        assert split_market_type("NFL_POINTS_ML", self.LEAGUES) == ("NFL", "POINTS_ML")

    def test_multitoken_league(self):
        assert split_market_type("BRASILEIRAO_SERIE_B_GOALS_ML3WAY", self.LEAGUES) == (
            "BRASILEIRAO_SERIE_B",
            "GOALS_ML3WAY",
        )

    def test_longest_prefix_wins(self):
        # VNL_WOMEN must not be claimed by VNL.
        assert split_market_type("VNL_WOMEN_POINTS_OU", self.LEAGUES) == (
            "VNL_WOMEN",
            "POINTS_OU",
        )
        assert split_market_type("VNL_POINTS_OU", self.LEAGUES) == ("VNL", "POINTS_OU")

    def test_case_insensitive(self):
        assert split_market_type("nfl_points_ml", self.LEAGUES) == ("NFL", "POINTS_ML")

    def test_unmatched(self):
        assert split_market_type("MLB_RUNS_ML", self.LEAGUES) == (None, None)


class TestHumanizeMarketType(unittest.TestCase):
    def test_core_markets(self):
        assert humanize_market_type("POINTS_ML") == "Moneyline"
        assert humanize_market_type("GOALS_ML3WAY") == "Match Result (3-Way)"
        assert humanize_market_type("POINTS_SP") == "Spread"
        assert humanize_market_type("GOALS_OU") == "Total"
        assert humanize_market_type("RUNS_OU") == "Total"

    def test_overrides(self):
        assert humanize_market_type("BTTS") == "Both Teams to Score"
        assert humanize_market_type("RUN_LINE") == "Run Line"
        assert humanize_market_type("PUCK_LINE") == "Puck Line"

    def test_props(self):
        assert humanize_market_type("PASSING_YARDS_OU") == "Passing Yards O/U"
        assert humanize_market_type("BATTING_HOMERUNS_YN") == "Batting Homeruns Yes/No"
        assert humanize_market_type("POINTS_EO") == "Points Even/Odd"

    def test_empty(self):
        assert humanize_market_type("") == "Market"


class TestColumnSortKey(unittest.TestCase):
    def test_core_before_props_then_alpha(self):
        labels = ["Passing Yards O/U", "Total", "Moneyline", "Both Teams to Score", "Assists O/U"]
        assert sorted(labels, key=column_sort_key) == [
            "Moneyline",
            "Total",
            "Both Teams to Score",
            "Assists O/U",
            "Passing Yards O/U",
        ]


class TestBuildSportMatrix(unittest.TestCase):
    def test_columns_and_cells(self):
        leagues = [
            {"id": "NFL", "name": "NFL"},
            {"id": "NCAAF", "name": "NCAA Football"},
        ]
        market_types = [
            "NFL_POINTS_ML",
            "NFL_POINTS_OU",
            "NFL_PASSING_YARDS_OU",
            "NCAAF_POINTS_OU",
        ]
        matrix = build_sport_matrix(leagues, market_types)
        assert matrix["columns"] == ["Moneyline", "Total", "Passing Yards O/U"]
        assert matrix["rows"] == [
            {"league": "NFL", "cells": [True, True, True]},
            {"league": "NCAA Football", "cells": [False, True, False]},
        ]

    def test_league_with_no_markets_is_all_false(self):
        leagues = [{"id": "NFL", "name": "NFL"}, {"id": "NCAAF", "name": "NCAA Football"}]
        matrix = build_sport_matrix(leagues, ["NFL_POINTS_ML"])
        assert matrix["columns"] == ["Moneyline"]
        assert matrix["rows"][1] == {"league": "NCAA Football", "cells": [False]}

    def test_no_matching_markets_gives_empty_columns(self):
        leagues = [{"id": "NFL", "name": "NFL"}]
        assert build_sport_matrix(leagues, ["MLB_RUNS_ML"])["columns"] == []

    def test_falls_back_to_id_when_no_name(self):
        matrix = build_sport_matrix([{"id": "NFL"}], ["NFL_POINTS_ML"])
        assert matrix["rows"][0]["league"] == "NFL"
