"""Regression tests for invite acceptance (plan §7.5 items 1–2).

Covers:
- Tournament invite accept actually enrolls the user (was: confirmation
  email sent, no Player row created).
- Enrollment failure (full/closing tournament) surfaces a 400 and rolls
  the invite back to its sent state.
- Match-invite accept is single-shot (state guard + row lock).
- Private match invite creation validates the target user id.
- Tournament 2-day reminder passes the User, not the Player join row.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse

from core.mail.models import Invite, Notification
from core.match.models import Match
from core.match.tests.factories import (
    make_golden_seed_selection,
    make_user,
    mock_golden_seed,
)
from core.tournament.crons.TournamentReminder import Tournament2DayReminder
from core.tournament.models.tournament import Player, Tournament


def _make_tournament(days_out=10, max_players=4, name="t-test"):
    # TournamentManager.create wants a naive datetime (it make_aware()s it).
    return Tournament.objects.create(
        name=name,
        start_date=datetime.now() + timedelta(days=days_out),
        max_accepted_players=max_players,
    )


def _accept(client, invite_id):
    url = reverse("core-portal:invite-accept", args=[invite_id])
    return client.post(
        url,
        json.dumps({"action": "accept"}),
        content_type="application/json",
        secure=True,
    )


class TournamentInviteEnrollmentTests(TestCase):
    def test_accept_enrolls_player_and_consumes_invite(self):
        admin = make_user("tadmin")
        joiner = make_user("tjoiner")
        tournament = _make_tournament()
        invite = Invite.objects.create_invite(
            obj_id=tournament.id, player=joiner, invite_type="tournament", sender=admin,
        )

        self.client.force_login(joiner)
        resp = _accept(self.client, invite.id)

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Player.objects.filter(tournament=tournament, player=joiner).exists()
        )
        self.assertFalse(Invite.objects.filter(id=invite.id).exists())

    def test_accept_full_tournament_rejected_and_invite_survives(self):
        admin = make_user("fadmin")
        joiner = make_user("fjoiner")
        filler = make_user("ffiller")
        tournament = _make_tournament(max_players=1)
        Player.objects.create_player(tournament, filler)
        invite = Invite.objects.create_invite(
            obj_id=tournament.id, player=joiner, invite_type="tournament", sender=admin,
        )

        self.client.force_login(joiner)
        resp = _accept(self.client, invite.id)

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            Player.objects.filter(tournament=tournament, player=joiner).exists()
        )
        # Atomic rollback — the invite is back in its sent state.
        invite.refresh_from_db()
        self.assertEqual(invite.state, "sent")

    def test_accept_inside_three_day_window_rejected(self):
        admin = make_user("wadmin")
        joiner = make_user("wjoiner")
        tournament = _make_tournament(days_out=2)
        invite = Invite.objects.create_invite(
            obj_id=tournament.id, player=joiner, invite_type="tournament", sender=admin,
        )

        self.client.force_login(joiner)
        resp = _accept(self.client, invite.id)

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            Player.objects.filter(tournament=tournament, player=joiner).exists()
        )


class MatchInviteAcceptTests(TestCase):
    def test_second_accept_is_rejected_and_no_duplicate_match(self):
        sender = make_user("msender")
        receiver = make_user("mreceiver")
        invite = Invite.objects.create_invite(
            obj_id=None, player=receiver, invite_type="match", sender=sender,
        )
        golden = make_golden_seed_selection()

        self.client.force_login(receiver)
        with mock_golden_seed(golden):
            resp1 = _accept(self.client, invite.id)
            resp2 = _accept(self.client, invite.id)

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 404)
        self.assertEqual(
            Match.objects.filter(player_1=sender, player_2=receiver).count(), 1
        )

    def test_manager_state_guard_blocks_non_sent_invite(self):
        sender = make_user("gsender")
        receiver = make_user("greceiver")
        invite = Invite.objects.create_invite(
            obj_id=None, player=receiver, invite_type="match", sender=sender,
        )
        invite.state = "accepted"
        invite.save()

        with self.assertRaises(Invite.DoesNotExist):
            Invite.objects.accept_invite(invite)
        self.assertEqual(
            Match.objects.filter(player_1=sender, player_2=receiver).count(), 0
        )


class PrivateMatchInviteCreationTests(TestCase):
    URL_NAME = "core-portal:portal-create-public-match"

    def _create(self, user, player_value):
        self.client.force_login(user)
        url = reverse(self.URL_NAME)
        return self.client.post(
            url, {"type": "private", "player": player_value}, secure=True,
        )

    def test_unknown_player_id_returns_404_not_500(self):
        owner = make_user("cowner")
        resp = self._create(owner, str(uuid.uuid4()))
        self.assertEqual(resp.status_code, 404)

    def test_malformed_player_id_returns_404_not_500(self):
        owner = make_user("cmal")
        resp = self._create(owner, "not-a-uuid")
        self.assertEqual(resp.status_code, 404)

    def test_self_invite_rejected(self):
        owner = make_user("cself")
        resp = self._create(owner, str(owner.id))
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Invite.objects.filter(sender=owner).exists())

    def test_duplicate_pending_invite_reuses_existing(self):
        owner = make_user("cdup")
        target = make_user("cdup2")
        resp1 = self._create(owner, str(target.id))
        resp2 = self._create(owner, str(target.id))

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(
            Invite.objects.filter(sender=owner, player=target, type="match").count(), 1
        )
        self.assertEqual(
            resp1.json()["invite_id"], resp2.json()["invite_id"]
        )


class TournamentReminderTests(TestCase):
    def test_reminder_notifies_user_not_player_row(self):
        user = make_user("remind")
        tournament = _make_tournament()
        Player.objects.create_player(tournament, user)

        # Was: Emails.send_tournament_starting_notification(player_row, ...)
        # -> ValueError("Invalid user instance") on every run.
        Tournament2DayReminder().send_players_Email(tournament)

        self.assertTrue(
            Notification.objects.filter(
                user=user, message__icontains=tournament.name
            ).exists()
        )
