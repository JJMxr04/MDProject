"""Phase 8 increment 4 — leaderboard standings + the page view."""

from __future__ import annotations

from datetime import date

from django.test import TestCase
from django.urls import reverse

from core.match.tests.factories import make_user
from core.ranking import constants, standings
from core.ranking.models import PlayerProgress, Season, SeasonParticipation


def _season(status=Season.Status.ACTIVE):
    s = Season(name="Q1", status=status, start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))
    s.save()
    return s


def _part(season, *, points, wins=0, losses=0, games=5, division=1, final_rank=None):
    return SeasonParticipation.objects.create(
        user=make_user(), season=season, season_points=points,
        wins=wins, losses=losses, games_played=games, division=division,
        final_rank=final_rank,
    )


class SeasonStandingsTests(TestCase):
    def test_live_season_orders_by_points(self):
        s = _season()
        _part(s, points=100)
        top = _part(s, points=300)
        _part(s, points=200)
        rows = standings.season_leaderboard(s)
        self.assertEqual(rows[0]["user"], top.user)
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3])

    def test_eligibility_floor_excludes_thin_records(self):
        s = _season()
        _part(s, points=999, games=constants.SEASON_ELIGIBILITY_FLOOR - 1)
        ok = _part(s, points=10, games=constants.SEASON_ELIGIBILITY_FLOOR)
        rows = standings.season_leaderboard(s)
        self.assertEqual([r["user"] for r in rows], [ok.user])

    def test_closed_season_uses_frozen_final_rank(self):
        s = _season(status=Season.Status.CLOSED)
        # final_rank, not live points, drives a closed board.
        a = _part(s, points=50, games=6, final_rank=1)
        b = _part(s, points=500, games=6, final_rank=2)
        rows = standings.season_leaderboard(s)
        self.assertEqual([r["user"] for r in rows], [a.user, b.user])

    def test_division_filter(self):
        s = _season()
        d1 = _part(s, points=100, division=1)
        _part(s, points=100, division=2)
        rows = standings.season_leaderboard(s, division=1)
        self.assertEqual([r["user"] for r in rows], [d1.user])


class GlobalStandingsTests(TestCase):
    def test_orders_by_global_points(self):
        u1, u2 = make_user(), make_user()
        PlayerProgress.objects.create(user=u1, global_points=100, level=2)
        PlayerProgress.objects.create(user=u2, global_points=500, level=5)
        rows = standings.global_leaderboard()
        self.assertEqual(rows[0]["user"], u2)
        self.assertEqual(rows[0]["rank"], 1)


class LeaderboardViewTests(TestCase):
    def setUp(self):
        self.user = make_user("viewer")
        self.client.force_login(self.user)

    def test_season_scope_renders(self):
        s = _season()
        _part(s, points=120, games=5)
        resp = self.client.get(reverse("core-portal:portal-leaderboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Leaderboard")

    def test_global_scope_renders(self):
        PlayerProgress.objects.create(user=self.user, global_points=42, level=2)
        resp = self.client.get(reverse("core-portal:portal-leaderboard") + "?scope=global")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Career")
