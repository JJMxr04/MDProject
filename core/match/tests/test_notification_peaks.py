"""Notifications at emotional peaks, each firing exactly once.

1. Golden-game picks route through the debounced (match, picker) summary.
2. "Your golden pick hit" fires once across BOTH settlement paths (signal
   + bulk propagate), never on re-settle/replay, never on completed matches.
3. "Settles tonight" one-shot: scheduled at end_date - 6h from accept,
   skipped at execution if the match already completed.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob

from core.event.odds.settlement import propagate_to_matches
from core.game.models import Game
from core.game.tasks import send_pick_summary
from core.mail.models import Notification
from core.match.models import Match
from core.match.tasks import match_settles_tonight, schedule_settles_tonight
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
    settle_selection,
)


def _email_jobs(subject_contains=None):
    jobs = ProcrastinateJob.objects.filter(task_name="core.mail.send_email")
    if subject_contains:
        jobs = [j for j in jobs if subject_contains in j.args.get("subject", "")]
        return jobs
    return jobs


class GoldenMatchBase(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        league = make_league("GOLDEN")
        self.golden_event = make_event(
            league, start_time=timezone.now() + timedelta(days=2),
        )
        self.market, self.g_home, self.g_away = make_two_way_market(self.golden_event)
        self.match = make_match(self.p1, self.p2, golden_selection=self.g_home)
        self.golden = self.match.games.get(is_golden=True)


class GoldenPickSummaryTests(GoldenMatchBase):
    def test_golden_pick_schedules_debounced_summary(self):
        before = ProcrastinateJob.objects.filter(
            task_name="core.game.send_pick_summary",
        ).count()
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=40,
        )
        after = ProcrastinateJob.objects.filter(
            task_name="core.game.send_pick_summary",
        ).count()
        self.assertEqual(after - before, 1)

    def test_summary_counts_golden_alongside_regulars(self):
        # One golden pick by p1, zero regular picks → count 1, one email.
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=40,
        )
        count = send_pick_summary(
            str(self.match.id), str(self.p1.id), str(self.p2.id),
        )
        self.assertEqual(count, 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.p2, message__icontains="pick",
            ).exists()
        )

    def test_opponent_golden_pick_counts_their_side_only(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p2, game_id=self.golden.id,
            selection_id=self.g_away.id, tiebreaker_total=38,
        )
        # p1 has made no picks → their summary would be zero → no email.
        count = send_pick_summary(
            str(self.match.id), str(self.p1.id), str(self.p2.id),
        )
        self.assertEqual(count, 0)
        # p2's summary counts the golden side they actually picked.
        count = send_pick_summary(
            str(self.match.id), str(self.p2.id), str(self.p1.id),
        )
        self.assertEqual(count, 1)


class GoldenHitPeakTests(GoldenMatchBase):
    def _pick_both(self):
        Game.objects.pick_on_locked_slot(
            current_user=self.p1, game_id=self.golden.id,
            selection_id=self.g_home.id, tiebreaker_total=40,
        )
        Game.objects.pick_on_locked_slot(
            current_user=self.p2, game_id=self.golden.id,
            selection_id=self.g_away.id, tiebreaker_total=38,
        )

    def test_signal_path_notifies_winner_once(self):
        self._pick_both()
        settle_selection(self.g_home, "WON")   # post_save → signal path
        settle_selection(self.g_away, "LOST")

        hits = _email_jobs("Golden Game pick hit")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].args["recipient"], self.p1.email)
        self.assertTrue(
            Notification.objects.filter(
                user=self.p1, message__icontains="Golden Game pick hit",
            ).exists()
        )
        # No notification for the losing side.
        self.assertFalse(
            Notification.objects.filter(
                user=self.p2, message__icontains="Golden Game pick hit",
            ).exists()
        )

        # Re-save / re-settle replay → claim already taken, nothing new.
        settle_selection(self.g_home, "WON")
        self.assertEqual(len(_email_jobs("Golden Game pick hit")), 1)

    def test_bulk_path_notifies_once_and_replay_is_silent(self):
        self._pick_both()
        # Settle WITHOUT signals (queryset update) — the bulk-settlement shape.
        type(self.g_home).objects.filter(pk=self.g_home.pk).update(
            settlement_status="WON",
        )
        propagate_to_matches(self.golden_event)
        self.assertEqual(len(_email_jobs("Golden Game pick hit")), 1)

        # Webhook redelivery / nightly backfill re-walk → still one.
        propagate_to_matches(self.golden_event)
        self.assertEqual(len(_email_jobs("Golden Game pick hit")), 1)

    def test_completed_match_gets_no_golden_hit(self):
        self._pick_both()
        Match.objects.filter(pk=self.match.pk).update(match_state="completed")
        type(self.g_home).objects.filter(pk=self.g_home.pk).update(
            settlement_status="WON",
        )
        propagate_to_matches(self.golden_event)
        self.assertEqual(len(_email_jobs("Golden Game pick hit")), 0)

    def test_no_winner_no_notification(self):
        self._pick_both()
        settle_selection(self.g_home, "LOST")
        settle_selection(self.g_away, "VOID")
        self.assertEqual(len(_email_jobs("Golden Game pick hit")), 0)


class SettlesTonightTests(TestCase):
    def _jobs(self):
        return ProcrastinateJob.objects.filter(task_name="core.match.settles_tonight")

    def test_accept_schedules_one_shot_at_end_minus_six_hours(self):
        p1, p2 = make_user("s1"), make_user("s2")
        match = make_match(p1, p2)  # accept_match ran inside the factory
        jobs = list(self._jobs())
        self.assertEqual(len(jobs), 1)
        match.refresh_from_db()
        # The factory rewrites end_date after accept; compare against the
        # end_date the accept saw (now + MARATHON window) within tolerance.
        expected = timezone.now() + timedelta(days=7) - timedelta(hours=6)
        delta = abs((jobs[0].scheduled_at - expected).total_seconds())
        self.assertLess(delta, 120)

    def test_rescheduling_is_absorbed_by_queueing_lock(self):
        p1, p2 = make_user("s3"), make_user("s4")
        match = make_match(p1, p2)
        self.assertEqual(self._jobs().count(), 1)
        self.assertFalse(schedule_settles_tonight(match))
        self.assertEqual(self._jobs().count(), 1)

    def test_window_too_short_schedules_nothing(self):
        p1, p2 = make_user("s5"), make_user("s6")
        match = make_match(p1, p2)
        self._jobs().delete()
        match.end_date = timezone.now() + timedelta(hours=2)  # < 6h out
        match.save(update_fields=["end_date"])
        self.assertFalse(schedule_settles_tonight(match))
        self.assertEqual(self._jobs().count(), 0)

    def test_task_notifies_both_players(self):
        p1, p2 = make_user("s7"), make_user("s8")
        match = make_match(p1, p2)
        sent = match_settles_tonight(str(match.id))
        self.assertEqual(sent, 2)
        for user in (p1, p2):
            self.assertTrue(
                Notification.objects.filter(
                    user=user, message__icontains="settles tonight",
                ).exists()
            )

    def test_completed_match_sends_nothing(self):
        p1, p2 = make_user("s9"), make_user("s10")
        match = make_match(p1, p2)
        Match.objects.filter(pk=match.pk).update(match_state="completed")
        sent = match_settles_tonight(str(match.id))
        self.assertEqual(sent, 0)
        self.assertEqual(len(_email_jobs("settles tonight")), 0)
