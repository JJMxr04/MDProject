"""Unit tests for the portal card normalizers (cards.py)."""
from __future__ import annotations

import uuid

from django.test import SimpleTestCase, TestCase

from core.portal import cards
from core.match.tests.factories import make_event, make_league, make_team, make_user


class StatusTests(SimpleTestCase):
    def test_plain_states_unchanged(self):
        self.assertEqual(cards._status(is_live=False, is_final=False), "upcoming")
        self.assertEqual(cards._status(is_live=True, is_final=False), "live")
        self.assertEqual(cards._status(is_live=False, is_final=True), "final")

    def test_postponed_strings(self):
        for s in ("postponed", "Postponed", "POSTPONED", "delayed"):
            self.assertEqual(
                cards._status(is_live=False, is_final=False, status_type=s),
                "postponed", s,
            )

    def test_canceled_both_spellings(self):
        for s in ("canceled", "cancelled", "Canceled", "CANCELLED"):
            self.assertEqual(
                cards._status(is_live=False, is_final=False, status_type=s),
                "canceled", s,
            )

    def test_final_beats_postponed_and_canceled(self):
        self.assertEqual(
            cards._status(is_live=False, is_final=True, status_type="postponed"),
            "final",
        )
        self.assertEqual(
            cards._status(is_live=False, is_final=True, status_type="canceled"),
            "final",
        )

    def test_postponed_beats_live(self):
        self.assertEqual(
            cards._status(is_live=True, is_final=False, status_type="postponed"),
            "postponed",
        )


class FixtureFromDictTests(SimpleTestCase):
    def test_upcoming_event_has_no_winner_and_no_scores(self):
        fx = cards.fixture_from_dict({
            "league": {"name": "NBA"},
            "start_time": "2030-01-01T19:30:00+00:00",
            "is_live": False, "is_finalized": False,
            # Absolute URL so fixture_from_dict's absolutize_logo_url is a
            # no-op (the relative->absolute path is covered by
            # AbsolutizeLogoUrlTests); this test is about winner/scores.
            "home_team": {"name": "Mavericks", "logo_url": "http://agg/m.png"},
            "away_team": {"name": "Celtics", "logo_url": None},
            "home_score": None, "away_score": None,
            "winner": "Mavericks", "status_type": "notstarted",
        })
        self.assertEqual(fx["status"], "upcoming")
        self.assertEqual(fx["league_name"], "NBA")
        self.assertEqual(fx["home"]["name"], "Mavericks")
        self.assertEqual(fx["home"]["logo_url"], "http://agg/m.png")
        self.assertEqual(fx["away"]["logo_url"], "")
        self.assertIsNone(fx["winner_label"])

    def test_finished_event_exposes_score_and_winner(self):
        fx = cards.fixture_from_dict({
            "league": {"name": "NBA"},
            "start_time": "2020-01-01T19:30:00+00:00",
            "is_finalized": True,
            "home_team": {"name": "Mavericks"}, "away_team": {"name": "Celtics"},
            "home_score": 112, "away_score": 108,
            "winner": "Mavericks", "status_type": "finished",
        })
        self.assertEqual(fx["status"], "final")
        self.assertEqual(fx["home"]["score"], 112)
        self.assertEqual(fx["away"]["score"], 108)
        self.assertEqual(fx["winner_label"], "Mavericks")

    def test_live_event_status(self):
        fx = cards.fixture_from_dict({"is_live": True, "home_team": {}, "away_team": {}})
        self.assertEqual(fx["status"], "live")

    def test_postponed_status_type(self):
        fx = cards.fixture_from_dict({
            "status_type": "postponed", "home_team": {}, "away_team": {},
        })
        self.assertEqual(fx["status"], "postponed")

    def test_canceled_status_type(self):
        fx = cards.fixture_from_dict({
            "status_type": "canceled", "home_team": {}, "away_team": {},
        })
        self.assertEqual(fx["status"], "canceled")

    def test_missing_team_name_falls_back_to_tbd(self):
        fx = cards.fixture_from_dict({"home_team": {}, "away_team": {}})
        self.assertEqual(fx["home"]["name"], "TBD")

    def test_none_input_returns_none(self):
        self.assertIsNone(cards.fixture_from_dict(None))


class FixtureFromEventTests(TestCase):
    def test_finished_event_model_maps_score_and_winner(self):
        league = make_league()
        home = make_team(league, "DAL", name="Mavericks")
        away = make_team(league, "BOS", name="Celtics")
        event = make_event(
            league, home=home, away=away, status_type="finished",
            is_finalized=True, home_score=112, away_score=108,
        )
        fx = cards.fixture_from_event(event)
        self.assertEqual(fx["status"], "final")
        self.assertEqual(fx["league_name"], league.name)
        self.assertEqual(fx["home"]["name"], "Mavericks")
        self.assertEqual(fx["home"]["score"], 112)
        self.assertEqual(fx["winner_label"], "Mavericks")

    def test_postponed_event_model_status(self):
        league = make_league()
        home = make_team(league, "DAL", name="Mavericks")
        away = make_team(league, "BOS", name="Celtics")
        event = make_event(
            league, home=home, away=away, status_type="postponed",
        )
        fx = cards.fixture_from_event(event)
        self.assertEqual(fx["status"], "postponed")

    def test_none_event_returns_none(self):
        self.assertIsNone(cards.fixture_from_event(None))


class MatchOutcomeTests(TestCase):
    def test_pending_when_not_completed(self):
        u = make_user("a")
        match = type("M", (), {"match_state": "accepted", "winner_id": None})()
        self.assertEqual(cards.match_outcome(match, u)["state"], "pending")

    def test_won_lost_draw(self):
        u = make_user("a")
        you = type("M", (), {"match_state": "completed", "winner_id": u.id})()
        draw = type("M", (), {"match_state": "completed", "winner_id": None})()
        lost = type("M", (), {"match_state": "completed", "winner_id": uuid.uuid4()})()
        self.assertEqual(cards.match_outcome(you, u)["state"], "won")
        self.assertEqual(cards.match_outcome(draw, u)["state"], "draw")
        self.assertEqual(cards.match_outcome(lost, u)["state"], "lost")
