"""Duplicate-send fixes for match completion (plan §7.1 #4, Phase 3 §1).

Three layers under test:
  1. ``maybe_complete_match`` runs ``calculate_winner`` exactly once even
     under concurrent entry (row lock + state re-check).
  2. The email layer's queueing-lock dedupe (``dedupe_key``) drops a
     second result email for the same (match, recipient).
  3. The tournament bracket signal advances only on the transition into
     ``completed``, never on a re-save of a completed Match.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob

from core.event.models.odds.selection import SettlementStatus
from core.game.models.bet import Bet
from core.mail.models import Emails, Notification
from core.match.models import Match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_match,
    make_two_way_market,
    make_user,
)


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


def _give_p1_a_settled_win(match, p1, league):
    """Settle one p1-owned slot as WON/LOST so p1 leads 1–0."""
    game = match.games.filter(owner=p1, is_golden=False).order_by("slot").first()
    event = make_event(
        league, status_type="finished", is_finalized=True,
        home_score=10, away_score=7,
    )
    _, home_sel, away_sel = make_two_way_market(
        event, home_status=SettlementStatus.WON, away_status=SettlementStatus.LOST,
    )
    game.event = event
    game.save(update_fields=["event"])
    Bet.objects.set_owner_outcome(game.bet, home_sel)
    Bet.objects.set_player_2_outcome(game.bet, away_sel)


class CompletionIdempotencyTests(TestCase):
    def setUp(self):
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.league = make_league()
        _give_p1_a_settled_win(self.match, self.p1, self.league)
        # Close the window so maybe_complete_match finalizes on entry.
        self.match.end_date = timezone.now() - timedelta(hours=1)
        self.match.save(update_fields=["end_date"])

    def test_double_entry_sends_one_result_pair(self):
        before = _email_jobs().count()
        Match.objects.maybe_complete_match(self.match)
        # Second entry with the same (stale) instance — state re-check
        # under the lock must make it a no-op.
        Match.objects.maybe_complete_match(self.match)

        self.match.refresh_from_db()
        self.assertEqual(self.match.match_state, "completed")
        self.assertEqual(self.match.winner, self.p1)
        # One victory (p1) + one lost (p2) — not two pairs.
        self.assertEqual(_email_jobs().count() - before, 2)

    def test_email_layer_dedupe_key_drops_second_send(self):
        before = _email_jobs().count()
        Emails.send_match_victory_notification(self.p1, "rival", match_id=self.match.id)
        Emails.send_match_victory_notification(self.p1, "rival", match_id=self.match.id)
        self.assertEqual(_email_jobs().count() - before, 1)


class CompletionConcurrencyTests(TransactionTestCase):
    """Two simultaneous settle calls produce exactly one victory email."""

    def test_concurrent_completion_sends_once(self):
        p1 = make_user("c1")
        p2 = make_user("c2")
        match = make_match(p1, p2)
        league = make_league("NBA")
        _give_p1_a_settled_win(match, p1, league)
        match.end_date = timezone.now() - timedelta(hours=1)
        match.save(update_fields=["end_date"])

        barrier = threading.Barrier(2)
        errors = []

        def settle():
            try:
                barrier.wait(timeout=10)
                fresh = Match.objects.get(pk=match.pk)
                Match.objects.maybe_complete_match(fresh)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=settle) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(errors, [])
        match.refresh_from_db()
        self.assertEqual(match.match_state, "completed")
        victory_jobs = [
            j for j in _email_jobs()
            if j.args["recipient"] == p1.email and "Won the Match" in j.args["subject"]
        ]
        self.assertEqual(len(victory_jobs), 1)
        # Exactly two RESULT notifications (one per player), not doubled by the
        # concurrent completion. Level-up notifications from the phase-8 engine
        # also land here (created once, under the same lock) — exclude them so
        # this stays a dedupe assertion on the result emails.
        result_notifs = (
            Notification.objects.filter(user__in=[p1, p2])
            .exclude(message__icontains="level")
            .count()
        )
        self.assertEqual(result_notifs, 2)


class TournamentSignalTransitionTests(TestCase):
    def test_resave_of_completed_match_fires_nothing(self):
        from core.tournament.models.tournament import Player, Round, Tournament

        p1 = make_user("t1")
        p2 = make_user("t2")
        match = make_match(p1, p2)
        tournament = Tournament.objects.create("Signal Test Cup", datetime.now(), 2)
        pl1 = Player.objects.create_player(tournament, p1)
        pl2 = Player.objects.create_player(tournament, p2)
        final = Round.objects.create(
            tournament=tournament, level_num=0, match=match,
            player_1=pl1, player_2=pl2,
        )

        match.winner = p1
        match.match_state = "completed"
        match.save(update_fields=["winner", "match_state"])

        final.refresh_from_db()
        self.assertTrue(final.completed)
        self.assertEqual(final.winner, pl1)
        jobs_after_first = _email_jobs().count()
        victory_subjects = [
            j for j in _email_jobs() if "Tournament" in j.args["subject"]
        ]
        self.assertEqual(len(victory_subjects), 1)

        # Any later re-save of the (already completed) match must not
        # re-advance the bracket or re-send the victory email.
        match.save()

        self.assertEqual(_email_jobs().count(), jobs_after_first)
        final.refresh_from_db()
        self.assertEqual(final.winner, pl1)
