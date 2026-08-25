"""Season lifecycle: close, freeze ranks, badges +
finish bonuses, promotion/relegation, activation, missing-season warning.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.test import TestCase

from core.mail.models.notifications import Notification
from core.match.tests.factories import make_user
from core.ranking import constants, lifecycle
from core.ranking.models import (
    Badge,
    PlayerProgress,
    Season,
    SeasonParticipation,
    XpEvent,
)


def _season(name, status, start, end):
    s = Season(name=name, status=status, start_date=start, end_date=end)
    s.save()  # bypass full_clean — tests construct deliberate states
    return s


def _participant(season, *, points, wins, losses, games, division=1):
    return SeasonParticipation.objects.create(
        user=make_user(), season=season, season_points=points,
        wins=wins, losses=losses, games_played=games, division=division,
    )


class CloseSeasonTests(TestCase):
    def setUp(self):
        self.season = _season("Q1", Season.Status.ACTIVE, date(2026, 1, 1), date(2026, 3, 31))

    def test_close_freezes_ranks_and_awards_top_three(self):
        # Four eligible players, descending points.
        p1 = _participant(self.season, points=300, wins=6, losses=0, games=6)
        p2 = _participant(self.season, points=200, wins=4, losses=2, games=6)
        p3 = _participant(self.season, points=100, wins=2, losses=4, games=6)
        p4 = _participant(self.season, points=50, wins=1, losses=5, games=6)

        lifecycle.close_season(self.season)
        self.season.refresh_from_db()
        self.assertEqual(self.season.status, Season.Status.CLOSED)

        for p, rank in ((p1, 1), (p2, 2), (p3, 3), (p4, 4)):
            p.refresh_from_db()
            self.assertEqual(p.final_rank, rank)

        # #1 gets division-winner + top-three; #2/#3 get top-three only.
        self.assertTrue(Badge.objects.filter(user=p1.user, type=Badge.Type.DIVISION_WINNER).exists())
        self.assertTrue(Badge.objects.filter(user=p1.user, type=Badge.Type.TOP_THREE).exists())
        self.assertTrue(Badge.objects.filter(user=p3.user, type=Badge.Type.TOP_THREE).exists())
        self.assertFalse(Badge.objects.filter(user=p4.user).exists())

        # Finish bonus credits global points + XP for the top three only.
        self.assertEqual(
            PlayerProgress.objects.get(user=p1.user).global_points,
            constants.PTS_SEASON_FINISH_TOP3,
        )
        self.assertTrue(XpEvent.objects.filter(user=p2.user, source=XpEvent.Source.SEASON_FINISH).exists())
        self.assertFalse(PlayerProgress.objects.filter(user=p4.user, global_points__gt=0).exists())

    def test_ineligible_players_are_not_ranked(self):
        # Below the games floor → excluded from standings entirely.
        thin = _participant(self.season, points=999, wins=1, losses=0,
                            games=constants.SEASON_ELIGIBILITY_FLOOR - 1)
        lifecycle.close_season(self.season)
        thin.refresh_from_db()
        self.assertIsNone(thin.final_rank)
        self.assertFalse(Badge.objects.filter(user=thin.user).exists())

    def test_small_population_stays_division_one(self):
        for _ in range(4):
            _participant(self.season, points=100, wins=3, losses=3, games=6)
        lifecycle.close_season(self.season)
        divisions = {p.current_division for p in PlayerProgress.objects.all()}
        self.assertEqual(divisions, {1})

    def test_large_population_splits_into_divisions(self):
        # Enough ranked players to trigger a split.
        n = constants.DIVISION_SPLIT_THRESHOLD + constants.DIVISION_SIZE
        for i in range(n):
            _participant(self.season, points=n - i, wins=3, losses=3, games=6)
        lifecycle.close_season(self.season)
        divisions = sorted({p.current_division for p in PlayerProgress.objects.all()})
        self.assertGreaterEqual(len(divisions), 2)
        self.assertEqual(divisions[0], 1)


class RunLifecycleTests(TestCase):
    def test_closes_ended_and_activates_due_draft(self):
        ended = _season("Q1", Season.Status.ACTIVE, date(2026, 1, 1), date(2026, 3, 31))
        _participant(ended, points=100, wins=3, losses=3, games=6)
        upcoming = _season("Q2", Season.Status.DRAFT, date(2026, 4, 1), date(2026, 6, 30))

        report = lifecycle.run_lifecycle(today=date(2026, 4, 2))

        ended.refresh_from_db()
        upcoming.refresh_from_db()
        self.assertEqual(ended.status, Season.Status.CLOSED)
        self.assertEqual(upcoming.status, Season.Status.ACTIVE)
        self.assertIn("q1", report["closed"])
        self.assertIn("q2", report["activated"])

    def test_activation_notifies_engaged_players(self):
        # A player with a progress row exists (engaged); a brand-new DRAFT is due.
        # (Every user gets a PlayerProgress at signup, so just create the user.)
        make_user("engaged")
        draft = _season("Q1", Season.Status.DRAFT, date(2026, 1, 1), date(2026, 3, 31))
        lifecycle.run_lifecycle(today=date(2026, 1, 2))
        draft.refresh_from_db()
        self.assertEqual(draft.status, Season.Status.ACTIVE)
        self.assertTrue(Notification.objects.filter(message__icontains="season").exists())

    def test_warns_when_no_next_season_scheduled(self):
        # Active season ends within the warning window, nothing queued behind it.
        soon = date(2026, 1, 5)
        _season("Q1", Season.Status.ACTIVE, date(2026, 1, 1), soon + timedelta(days=3))
        report = lifecycle.run_lifecycle(today=soon)
        self.assertTrue(report["warned"])

    def test_no_warning_when_next_is_scheduled(self):
        soon = date(2026, 1, 5)
        _season("Q1", Season.Status.ACTIVE, date(2026, 1, 1), soon + timedelta(days=3))
        _season("Q2", Season.Status.DRAFT, soon + timedelta(days=10), soon + timedelta(days=100))
        report = lifecycle.run_lifecycle(today=soon)
        self.assertFalse(report["warned"])
