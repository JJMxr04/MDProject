"""Progression backbone: model validation + the
points/XP/Elo crediting engine.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.mail.models.notifications import Notification
from core.match.models import Match
from core.match.tests.factories import make_user
from core.ranking import constants, engine
from core.ranking.models import (
    PlayerProgress,
    Season,
    SeasonParticipation,
    XpEvent,
)


def _season(status=Season.Status.ACTIVE, start=(2026, 1, 1), end=(2026, 3, 31)):
    s = Season(name=f"Season {start}", status=status,
               start_date=date(*start), end_date=date(*end))
    s.full_clean()
    s.save()
    return s


class SeasonValidationTests(TestCase):
    def test_end_must_be_after_start(self):
        s = Season(name="Bad", start_date=date(2026, 5, 1), end_date=date(2026, 5, 1))
        with self.assertRaises(ValidationError):
            s.full_clean()

    def test_only_one_active_season(self):
        _season(status=Season.Status.ACTIVE, start=(2026, 1, 1), end=(2026, 3, 31))
        dupe = Season(name="Second", status=Season.Status.ACTIVE,
                      start_date=date(2026, 4, 1), end_date=date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            dupe.full_clean()

    def test_overlapping_ranges_rejected(self):
        _season(status=Season.Status.DRAFT, start=(2026, 1, 1), end=(2026, 3, 31))
        overlap = Season(name="Overlap", status=Season.Status.DRAFT,
                         start_date=date(2026, 3, 15), end_date=date(2026, 6, 30))
        with self.assertRaises(ValidationError):
            overlap.full_clean()

    def test_non_overlapping_seasons_allowed(self):
        _season(status=Season.Status.ACTIVE, start=(2026, 1, 1), end=(2026, 3, 31))
        nxt = Season(name="Q2", status=Season.Status.DRAFT,
                     start_date=date(2026, 4, 1), end_date=date(2026, 6, 30))
        nxt.full_clean()  # no raise
        self.assertEqual(Season.active().name, "Season (2026, 1, 1)")


@override_settings(USE_AGGRIGATOR=False)
class EngineTests(TestCase):
    def _match(self, fmt="MARATHON", winner_is_p1=True):
        p1, p2 = make_user(), make_user()
        m = Match.objects.create(
            player_1=p1, player_2=p2, winner=p1 if winner_is_p1 else p2,
            format=fmt, match_state="completed",
        )
        return m, p1, p2

    def test_match_credits_both_players_once(self):
        season = _season()
        m, p1, p2 = self._match()
        engine.record_match_result(m)

        prog1 = PlayerProgress.objects.get(user=p1)
        prog2 = PlayerProgress.objects.get(user=p2)
        self.assertGreater(prog1.xp, 0)
        self.assertGreater(prog2.xp, 0)
        self.assertGreater(prog1.global_points, prog2.global_points)  # winner earns more
        self.assertEqual(prog1.lifetime_wins, 1)
        self.assertEqual(prog2.lifetime_losses, 1)
        # Season counters move too.
        sp1 = SeasonParticipation.objects.get(user=p1, season=season)
        self.assertGreater(sp1.season_points, 0)
        self.assertEqual(sp1.wins, 1)

        # Idempotent: a replay credits nothing more.
        xp_before = prog1.xp
        engine.record_match_result(m)
        prog1.refresh_from_db()
        self.assertEqual(prog1.xp, xp_before)

    def test_marathon_out_earns_blitz(self):
        blitz, bp1, _ = self._match(fmt="BLITZ")
        marathon, mp1, _ = self._match(fmt="MARATHON")
        engine.record_match_result(blitz)
        engine.record_match_result(marathon)
        self.assertGreater(
            PlayerProgress.objects.get(user=mp1).xp,
            PlayerProgress.objects.get(user=bp1).xp,
        )

    def test_winner_elo_rises_loser_falls(self):
        m, p1, p2 = self._match()
        engine.record_match_result(m)
        self.assertGreater(PlayerProgress.objects.get(user=p1).all_time_rating, constants.ELO_START)
        self.assertLess(PlayerProgress.objects.get(user=p2).all_time_rating, constants.ELO_START)

    def test_points_global_only_without_active_season(self):
        m, p1, p2 = self._match()  # no season created
        engine.record_match_result(m)
        self.assertGreater(PlayerProgress.objects.get(user=p1).global_points, 0)
        self.assertFalse(SeasonParticipation.objects.filter(user=p1).exists())

    def test_level_up_notifies(self):
        m, p1, p2 = self._match(fmt="MARATHON")
        before = Notification.objects.filter(user=p1).count()
        engine.record_match_result(m)
        prog = PlayerProgress.objects.get(user=p1)
        self.assertGreaterEqual(prog.level, 2)  # one marathon win clears level 1
        self.assertGreater(Notification.objects.filter(user=p1).count(), before)

    def test_duel_grants_xp_only(self):
        p1, p2 = make_user(), make_user()
        duel = Match.objects.create(
            player_1=p1, player_2=p2, winner=p1,
            match_type="duel", format="MARATHON", match_state="completed",
        )
        engine.grant_duel_xp(duel)
        prog = PlayerProgress.objects.get(user=p1)
        self.assertEqual(prog.xp, constants.XP_DUEL_WON)
        # Ladder-exempt: no points, no rating change, no lifetime W/L.
        self.assertEqual(prog.global_points, 0)
        self.assertEqual(prog.all_time_rating, constants.ELO_START)
        self.assertEqual(prog.lifetime_games, 0)
        self.assertFalse(SeasonParticipation.objects.filter(user=p1).exists())
        # Idempotent.
        engine.grant_duel_xp(duel)
        prog.refresh_from_db()
        self.assertEqual(prog.xp, constants.XP_DUEL_WON)

    def test_duel_draw_awards_nobody(self):
        p1, p2 = make_user(), make_user()
        duel = Match.objects.create(
            player_1=p1, player_2=p2, winner=None,
            match_type="duel", format="MARATHON", match_state="completed",
        )
        engine.grant_duel_xp(duel)
        self.assertFalse(PlayerProgress.objects.filter(user=p1, xp__gt=0).exists())


class LevelCurveTests(TestCase):
    def test_level_curve_is_monotonic_and_starts_at_one(self):
        self.assertEqual(constants.level_for_xp(0), 1)
        last = 0
        for xp in (100, 300, 1000, 5000):
            lvl = constants.level_for_xp(xp)
            self.assertGreaterEqual(lvl, last)
            last = lvl
