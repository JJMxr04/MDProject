"""Pick-email coalescing (plan §7.1 #5, Phase 3 §2).

Filling several slots in one sitting queues exactly ONE debounced
summary job per (match, picker); the job emails one "made N picks"
summary counted at send time.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from procrastinate.contrib.django.models import ProcrastinateJob

from core.game.models import Game
from core.game.tasks import send_pick_summary
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
)
from core.metrics.models import ProductEvent


def _summary_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.game.send_pick_summary")


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


class PickSummaryCoalescingTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.league = make_league()
        # Five distinct events (one event/market pair per slot allowed).
        self.picks = []
        for i in range(5):
            event = make_event(
                self.league, start_time=timezone.now() + timedelta(days=2),
            )
            _, home, _ = make_two_way_market(event)
            self.picks.append((event, home))

    def _upload_all(self):
        for event, selection in self.picks:
            Game.objects.upload_pick(
                current_user=self.p1,
                match=self.match,
                event_id=event.id,
                selection_id=selection.id,
            )

    def test_five_picks_queue_one_summary_job(self):
        self._upload_all()
        self.assertEqual(_summary_jobs().count(), 1)
        job = _summary_jobs().first()
        self.assertEqual(job.args["picker_id"], str(self.p1.pk))
        self.assertEqual(job.args["recipient_id"], str(self.p2.pk))
        # Debounced: scheduled out, not immediate.
        self.assertIsNotNone(job.scheduled_at)

    def test_summary_task_sends_one_email_with_count(self):
        self._upload_all()
        before = _email_jobs().count()

        sent = send_pick_summary(
            match_id=str(self.match.pk),
            picker_id=str(self.p1.pk),
            recipient_id=str(self.p2.pk),
        )

        self.assertEqual(sent, 5)
        jobs = _email_jobs()
        self.assertEqual(jobs.count() - before, 1)
        job = jobs.order_by("-id").first()
        self.assertEqual(job.args["recipient"], self.p2.email)
        self.assertIn("5 picks", job.args["subject"])
        self.assertEqual(job.args["context"]["pick_count"], 5)

    def test_no_per_pick_emails_fire(self):
        before = _email_jobs().count()
        self._upload_all()
        # No immediate "opponent uploaded a pick" emails — only the
        # (not yet run) summary job exists.
        self.assertEqual(_email_jobs().count(), before)

    def test_opponent_pick_gets_its_own_summary_key(self):
        self._upload_all()
        # p2 responds on p1's first claimed slot — opponent flow.
        event, _ = self.picks[0]
        market = event.markets.first()
        away = market.selections.exclude(
            pk=self.match.games.filter(owner=self.p1, event=event)
            .first().bet.owner_outcome_id
        ).first()
        Game.objects.upload_pick(
            current_user=self.p2,
            match=self.match,
            event_id=event.id,
            selection_id=away.id,
        )
        # One job per (match, picker): p1's batch + p2's response.
        self.assertEqual(_summary_jobs().count(), 2)

    def test_pick_made_events_tracked(self):
        self._upload_all()
        self.assertEqual(
            ProductEvent.objects.filter(user=self.p1, name="pick_made").count(), 5,
        )
