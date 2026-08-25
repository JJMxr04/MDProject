"""POTD feeds points/XP (not Elo)."""

from __future__ import annotations

from datetime import date

from django.test import TestCase

from core.match.tests.factories import make_user
from core.potd.models import DailyPick, DailyPickResult
from core.potd.tests.test_potd import make_potd
from core.ranking import constants, engine
from core.ranking.models import PlayerProgress, Season, SeasonParticipation, XpEvent


def _active_season():
    s = Season(name="Q1", status=Season.Status.ACTIVE,
               start_date=date(2026, 1, 1), end_date=date(2026, 3, 31))
    s.save()
    return s


class PotdPickCreditTests(TestCase):
    def test_recording_a_pick_credits_points_and_xp(self):
        season = _active_season()
        potd, home, _ = make_potd()
        user = make_user("picker")
        DailyPick.objects.record_pick(user=user, potd=potd, selection=home)

        prog = PlayerProgress.objects.get(user=user)
        self.assertEqual(prog.xp, constants.XP_POTD_PICK_MADE)
        self.assertEqual(prog.global_points, constants.PTS_POTD_PARTICIPATION)
        # POTD never moves Elo.
        self.assertEqual(prog.all_time_rating, constants.ELO_START)
        sp = SeasonParticipation.objects.get(user=user, season=season)
        self.assertEqual(sp.potd_picks, 1)
        self.assertEqual(sp.season_points, constants.PTS_POTD_PARTICIPATION)

    def test_pick_credit_is_idempotent(self):
        potd, home, _ = make_potd()
        user = make_user("picker")
        pick = DailyPick.objects.record_pick(user=user, potd=potd, selection=home)
        engine.record_potd_pick(pick)  # replay
        self.assertEqual(PlayerProgress.objects.get(user=user).xp, constants.XP_POTD_PICK_MADE)

    def test_streak_milestone_awards_bonus(self):
        potd, home, _ = make_potd()
        user = make_user("streaker")
        user.potd_current_streak = 7  # crossing a milestone
        pick = DailyPick.objects.create(user=user, potd=potd, selection=home)
        engine.record_potd_pick(pick)
        prog = PlayerProgress.objects.get(user=user)
        self.assertEqual(prog.xp, constants.XP_POTD_PICK_MADE + constants.XP_POTD_STREAK[7])


class PotdWinCreditTests(TestCase):
    def test_settled_win_is_credited_once(self):
        season = _active_season()
        potd, home, away = make_potd()
        user = make_user("winner")
        DailyPick.objects.record_pick(user=user, potd=potd, selection=home)

        home.settlement_status = "WON"
        home.save()
        self.assertEqual(DailyPick.objects.sync_pending(), 1)

        credited = engine.credit_settled_potd()
        self.assertEqual(credited, 1)

        prog = PlayerProgress.objects.get(user=user)
        self.assertEqual(prog.xp, constants.XP_POTD_PICK_MADE + constants.XP_POTD_PICK_WON)
        self.assertEqual(
            prog.global_points,
            constants.PTS_POTD_PARTICIPATION + constants.PTS_POTD_WIN,
        )
        sp = SeasonParticipation.objects.get(user=user, season=season)
        self.assertEqual(sp.potd_wins, 1)

        # Replay credits nothing more.
        self.assertEqual(engine.credit_settled_potd(), 0)

    def test_lost_pick_is_not_credited_a_win(self):
        potd, home, away = make_potd()
        user = make_user("loser")
        DailyPick.objects.record_pick(user=user, potd=potd, selection=home)
        home.settlement_status = "LOST"
        home.save()
        DailyPick.objects.sync_pending()
        self.assertEqual(engine.credit_settled_potd(), 0)
        # Only the participation award stands.
        self.assertEqual(
            PlayerProgress.objects.get(user=user).global_points,
            constants.PTS_POTD_PARTICIPATION,
        )
