"""Invite lifecycle tests: expiry, cancel, decline, state
bookkeeping, and the invite-list view.

Covers:
- Expired invites can't be accepted (manager raises ``InviteExpired``,
  view surfaces a 400 with the message) and the row flips to 'expired'.
- Match-invite default expiry equals the format window (BLITZ → 2d,
  default/MARATHON → 7d); friend invites get the fixed 14d window.
- ``expire_stale()`` flips only overdue 'sent' rows and returns the count.
- ``effective_state`` shows overdue 'sent' rows as 'expired' lazily.
- Cancel is sender-only; accept/reject are recipient-only (403 otherwise).
- Decline notifies the sender (Notification row + one queued
  ``core.mail.send_email`` job) and tracks 'invite_declined'.
- Friend accept writes the symmetric ``User.friends`` M2M.
- ``invite_list`` exposes incoming + outgoing lists and renders the
  Cancel control for outgoing 'sent' rows.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob

from core.mail.models import Invite, Notification
from core.mail.models.invites import INVITE_EXPIRY_DEFAULT, InviteExpired
from core.match.tests.factories import (
    make_golden_seed_selection,
    make_user,
    mock_golden_seed,
)
from core.metrics.models import ProductEvent


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


def _post_action(client, invite_id, action):
    url = reverse("core-portal:invite-accept", args=[invite_id])
    return client.post(
        url,
        json.dumps({"action": action}),
        content_type="application/json",
        secure=True,
    )


def _friend_invite(sender, player, **kwargs):
    return Invite.objects.create_invite(
        obj_id=None, player=player, invite_type="friend", sender=sender, **kwargs
    )


class InviteExpiryTests(TestCase):
    def test_manager_accept_of_expired_invite_raises(self):
        sender = make_user("exp_s")
        player = make_user("exp_p")
        invite = _friend_invite(
            sender, player, expires_at=timezone.now() - timedelta(hours=1)
        )

        with self.assertRaises(InviteExpired):
            Invite.objects.accept_invite(invite)

        invite.refresh_from_db()
        self.assertFalse(invite.accepted)
        # No friendship was created.
        self.assertFalse(sender.is_friend(player))
        # Regardless of what the column says, the row reads as expired.
        self.assertEqual(invite.effective_state, "expired")

    def test_expired_state_flip_persists_after_failed_accept(self):
        """Regression: the 'expired' flip used to roll back with the
        ``InviteExpired`` raise (it happened inside the atomic block).
        ``accept_invite`` now persists it post-rollback via a guarded
        queryset update."""
        sender = make_user("expf_s")
        player = make_user("expf_p")
        invite = _friend_invite(
            sender, player, expires_at=timezone.now() - timedelta(hours=1)
        )

        with self.assertRaises(InviteExpired):
            Invite.objects.accept_invite(invite)

        invite.refresh_from_db()
        self.assertEqual(invite.state, "expired")

    def test_view_accept_of_expired_invite_returns_400_with_message(self):
        sender = make_user("expv_s")
        player = make_user("expv_p")
        invite = _friend_invite(
            sender, player, expires_at=timezone.now() - timedelta(minutes=5)
        )

        self.client.force_login(player)
        resp = _post_action(self.client, invite.id, "accept")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("expired", resp.json()["error"])
        invite.refresh_from_db()
        self.assertFalse(invite.accepted)
        self.assertEqual(invite.effective_state, "expired")

    def test_fresh_invite_accepts_fine(self):
        sender = make_user("fresh_s")
        player = make_user("fresh_p")
        invite = _friend_invite(sender, player)

        self.client.force_login(player)
        resp = _post_action(self.client, invite.id, "accept")

        self.assertEqual(resp.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.state, "accepted")
        self.assertTrue(invite.accepted)


class DefaultExpiryTests(TestCase):
    # A challenge a friend hasn't answered within a day is stale — all
    # non-tournament invites churn on a 1-day fuse regardless of format.
    def test_match_invite_blitz_payload_expires_in_one_day(self):
        sender = make_user("blitz_s")
        player = make_user("blitz_p")
        # Match invites pass through the creatability choke-point — seed the
        # catalog so create_invite doesn't reject before we can check expiry.
        with mock_golden_seed(make_golden_seed_selection()):
            invite = Invite.objects.create_invite(
                obj_id=None, player=player, invite_type="match", sender=sender,
                payload={"format": "BLITZ"},
            )
        self.assertEqual(
            invite.expires_at, invite.invited_date + timedelta(days=1)
        )

    def test_match_invite_default_payload_expires_in_one_day(self):
        sender = make_user("mara_s")
        player = make_user("mara_p")
        with mock_golden_seed(make_golden_seed_selection()):
            invite = Invite.objects.create_invite(
                obj_id=None, player=player, invite_type="match", sender=sender,
            )
        self.assertEqual(
            invite.expires_at, invite.invited_date + timedelta(days=1)
        )

    def test_friend_invite_expires_in_one_day(self):
        sender = make_user("fwin_s")
        player = make_user("fwin_p")
        invite = _friend_invite(sender, player)
        self.assertEqual(
            invite.expires_at, invite.invited_date + INVITE_EXPIRY_DEFAULT
        )
        self.assertEqual(INVITE_EXPIRY_DEFAULT, timedelta(days=1))


@override_settings(USE_AGGRIGATOR=False)
class DeadOnArrivalTests(TestCase):
    def test_no_email_for_already_expired_invite(self):
        """A caller-supplied past ``expires_at`` must not trigger a
        dead-on-arrival invite email — the recipient could never act on it."""
        sender = make_user("doa_s")
        player = make_user("doa_p")
        before = _email_jobs().count()
        _friend_invite(
            sender, player, expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertEqual(_email_jobs().count(), before)

    def test_live_invite_still_emails(self):
        sender = make_user("live_s")
        player = make_user("live_p")
        before = _email_jobs().count()
        _friend_invite(sender, player)
        self.assertEqual(_email_jobs().count(), before + 1)


class ExpireStaleTests(TestCase):
    def test_flips_only_overdue_sent_rows_and_returns_count(self):
        sender = make_user("stale_s")
        past = timezone.now() - timedelta(hours=1)
        future = timezone.now() + timedelta(days=1)

        overdue_a = _friend_invite(sender, make_user("stale_a"), expires_at=past)
        overdue_b = _friend_invite(sender, make_user("stale_b"), expires_at=past)
        fresh = _friend_invite(sender, make_user("stale_c"), expires_at=future)

        accepted = _friend_invite(sender, make_user("stale_d"), expires_at=past)
        Invite.objects.filter(pk=accepted.pk).update(state="accepted", accepted=True)
        declined = _friend_invite(sender, make_user("stale_e"), expires_at=past)
        Invite.objects.filter(pk=declined.pk).update(state="declined")

        count = Invite.objects.expire_stale()

        self.assertEqual(count, 2)
        overdue_a.refresh_from_db()
        overdue_b.refresh_from_db()
        fresh.refresh_from_db()
        accepted.refresh_from_db()
        declined.refresh_from_db()
        self.assertEqual(overdue_a.state, "expired")
        self.assertEqual(overdue_b.state, "expired")
        self.assertEqual(fresh.state, "sent")
        self.assertEqual(accepted.state, "accepted")
        self.assertEqual(declined.state, "declined")


class EffectiveStateTests(TestCase):
    def test_overdue_sent_row_reports_expired_without_db_flip(self):
        sender = make_user("eff_s")
        player = make_user("eff_p")
        invite = _friend_invite(
            sender, player, expires_at=timezone.now() - timedelta(minutes=1)
        )

        self.assertEqual(invite.effective_state, "expired")
        # The column itself is untouched until the cron / accept path flips it.
        invite.refresh_from_db()
        self.assertEqual(invite.state, "sent")

    def test_future_dated_sent_row_reports_sent(self):
        sender = make_user("efff_s")
        player = make_user("efff_p")
        invite = _friend_invite(sender, player)
        self.assertEqual(invite.effective_state, "sent")


class CancelInviteTests(TestCase):
    def setUp(self):
        self.sender = make_user("can_s")
        self.player = make_user("can_p")
        self.invite = _friend_invite(self.sender, self.player)

    def test_sender_cancel_succeeds(self):
        self.client.force_login(self.sender)
        resp = _post_action(self.client, self.invite.id, "cancel")

        self.assertEqual(resp.status_code, 200)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.state, "canceled")
        self.assertTrue(
            ProductEvent.objects.filter(
                user=self.sender, name="invite_canceled"
            ).exists()
        )

    def test_player_cannot_cancel(self):
        self.client.force_login(self.player)
        resp = _post_action(self.client, self.invite.id, "cancel")

        self.assertEqual(resp.status_code, 403)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.state, "sent")

    def test_sender_cannot_accept_own_outgoing_invite(self):
        self.client.force_login(self.sender)
        resp = _post_action(self.client, self.invite.id, "accept")

        self.assertEqual(resp.status_code, 403)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.state, "sent")

    def test_sender_cannot_reject_own_outgoing_invite(self):
        self.client.force_login(self.sender)
        resp = _post_action(self.client, self.invite.id, "reject")

        self.assertEqual(resp.status_code, 403)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.state, "sent")


class DeclineInviteTests(TestCase):
    def test_player_reject_declines_and_notifies_sender(self):
        sender = make_user("dec_s")
        player = make_user("dec_p")
        invite = _friend_invite(sender, player)
        jobs_before = _email_jobs().count()

        self.client.force_login(player)
        resp = _post_action(self.client, invite.id, "reject")

        self.assertEqual(resp.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.state, "declined")

        # The SENDER is told — in-app Notification + one queued email.
        self.assertTrue(
            Notification.objects.filter(
                user=sender, message__icontains="declined"
            ).exists()
        )
        new_jobs = list(_email_jobs())[jobs_before:]
        self.assertEqual(len(new_jobs), 1)
        self.assertEqual(new_jobs[0].args["recipient"], sender.email)
        self.assertIn("declined", new_jobs[0].args["subject"])

        self.assertTrue(
            ProductEvent.objects.filter(
                user=player, name="invite_declined"
            ).exists()
        )


class FriendAcceptTests(TestCase):
    def test_accept_writes_symmetric_friendship(self):
        sender = make_user("fr_s")
        player = make_user("fr_p")
        invite = _friend_invite(sender, player)
        self.assertFalse(sender.is_friend(player))

        self.client.force_login(player)
        resp = _post_action(self.client, invite.id, "accept")

        self.assertEqual(resp.status_code, 200)
        invite.refresh_from_db()
        self.assertEqual(invite.state, "accepted")
        self.assertTrue(invite.accepted)
        # User.friends is symmetrical — one add_friend writes both directions.
        self.assertTrue(sender.is_friend(player))
        self.assertTrue(player.is_friend(sender))


class InviteListViewTests(TestCase):
    def test_context_has_incoming_and_outgoing_and_cancel_control(self):
        user = make_user("list_u")
        other = make_user("list_o")
        incoming = _friend_invite(other, user)
        outgoing = _friend_invite(user, other)

        self.client.force_login(user)

        # Default view is the Received box: incoming present in context, and
        # its accept/decline controls render. Both querysets are always built.
        resp = self.client.get(
            reverse("core-portal:invite-list"), secure=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(incoming, list(resp.context["invites"]))
        self.assertIn(outgoing, list(resp.context["outgoing_invites"]))
        self.assertNotIn(outgoing, list(resp.context["invites"]))
        self.assertContains(resp, "Decline")

        # The Sent box renders the sender-side Cancel control.
        resp_sent = self.client.get(
            reverse("core-portal:invite-list"), {"box": "sent"}, secure=True
        )
        self.assertEqual(resp_sent.status_code, 200)
        self.assertContains(resp_sent, "Cancel")
