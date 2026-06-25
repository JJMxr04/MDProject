"""Tests for PendingInvite (invite-to-non-user, plan Phase 4 §3, D-4b).

Covers:
- Manager: create_pending idempotency (per inviter+email, within the
  expiry window), per-inviter rows, re-create after expiry.
- resolve_token: round-trip, tampered token, consumed row.
- consume_for_user: friend edge both directions, match-invite
  materialization with payload, consumed_at stamping, idempotent second
  call, 'signup_invite_consumed' metric, self-invite skip.
- RegisterForm.clean_email: pending invite bypasses the waitlist gate;
  without one (and without waitlist approval) registration is rejected.
- RegisterView end-to-end: ?invite=<token> GET (session + prefill) then
  POST registers, consumes, befriends, and leaves the match Invite waiting.
- Referral (?ref=<friend_code>): friend edge + 'referral_signup' metric,
  but NO waitlist bypass.

NB: RegisterView.post is rate-limited 5/h per client IP, so every POST in
this module rides a unique REMOTE_ADDR.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.auth.forms.register_form import RegisterForm
from core.auth.models.waitlist import WaitlistEntry
from core.auth.views.register_view import (
    PENDING_INVITE_SESSION_KEY,
    REFERRAL_SESSION_KEY,
)
from core.mail.models import Invite, PendingInvite
from core.match.tests.factories import (
    make_golden_seed_selection,
    mock_golden_seed,
)
from core.metrics.models import ProductEvent
from core.user.models import User

PASSWORD = "Str0ng-passw0rd!42"


def make_user(name):
    return User.objects.create_user(
        username=name, email=f"{name}@test.local", password=PASSWORD,
    )


def register_data(email, username="newplayer"):
    """Complete, valid RegisterForm payload for ``email``."""
    return {
        "username": username,
        "email": email,
        "first_name": "New",
        "last_name": "Player",
        "date_of_birth": "1990-01-01",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "age_confirmation": True,
    }


# USE_AGGRIGATOR=False everywhere: creating a User fires the billing
# post_save signal, which would POST to the aggrigator over HTTP.
@override_settings(USE_AGGRIGATOR=False)
class CreatePendingTests(TestCase):
    def test_create_pending_idempotent_for_same_inviter_and_email(self):
        inviter = make_user("idem_inviter")

        first, created_first = PendingInvite.objects.create_pending(
            inviter=inviter, email="Friend@Test.Local",
        )
        second, created_second = PendingInvite.objects.create_pending(
            inviter=inviter, email="friend@test.local",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        # Stored lowercased, single row.
        self.assertEqual(first.email, "friend@test.local")
        self.assertEqual(
            PendingInvite.objects.filter(email="friend@test.local").count(), 1
        )

    def test_different_inviter_gets_separate_row(self):
        inviter_a = make_user("sep_inviter_a")
        inviter_b = make_user("sep_inviter_b")

        a, created_a = PendingInvite.objects.create_pending(
            inviter=inviter_a, email="shared@test.local",
        )
        b, created_b = PendingInvite.objects.create_pending(
            inviter=inviter_b, email="shared@test.local",
        )

        self.assertTrue(created_a)
        self.assertTrue(created_b)
        self.assertNotEqual(a.pk, b.pk)
        self.assertEqual(
            PendingInvite.objects.valid_for_email("shared@test.local").count(), 2
        )

    def test_expired_row_allows_a_fresh_pending(self):
        inviter = make_user("exp_inviter")
        stale, _ = PendingInvite.objects.create_pending(
            inviter=inviter, email="expired@test.local",
        )
        stale.expires_at = timezone.now() - timedelta(minutes=1)
        stale.save(update_fields=["expires_at"])

        fresh, created = PendingInvite.objects.create_pending(
            inviter=inviter, email="expired@test.local",
        )

        self.assertTrue(created)
        self.assertNotEqual(fresh.pk, stale.pk)
        self.assertTrue(fresh.is_valid)
        self.assertFalse(stale.is_valid)

    def test_valid_for_email_is_case_insensitive(self):
        inviter = make_user("case_inviter")
        pending, _ = PendingInvite.objects.create_pending(
            inviter=inviter, email="case@test.local",
        )

        rows = PendingInvite.objects.valid_for_email("CASE@TEST.LOCAL")

        self.assertEqual(list(rows), [pending])


@override_settings(USE_AGGRIGATOR=False)
class ResolveTokenTests(TestCase):
    def setUp(self):
        self.inviter = make_user("tok_inviter")
        self.pending, _ = PendingInvite.objects.create_pending(
            inviter=self.inviter, email="token@test.local",
        )

    def test_token_round_trips(self):
        resolved = PendingInvite.objects.resolve_token(self.pending.token)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.pk, self.pending.pk)

    def test_tampered_token_returns_none(self):
        token = self.pending.token
        flipped = "A" if token[-1] != "A" else "B"
        tampered = token[:-1] + flipped
        self.assertIsNone(PendingInvite.objects.resolve_token(tampered))

    def test_garbage_token_returns_none(self):
        self.assertIsNone(PendingInvite.objects.resolve_token("not-a-token"))

    def test_consumed_row_returns_none(self):
        token = self.pending.token
        self.pending.consumed_at = timezone.now()
        self.pending.save(update_fields=["consumed_at"])
        self.assertIsNone(PendingInvite.objects.resolve_token(token))


@override_settings(USE_AGGRIGATOR=False)
class ConsumeForUserTests(TestCase):
    def test_consume_befriends_materializes_match_invite_and_tracks(self):
        friend_inviter = make_user("cons_friend_inviter")
        match_inviter = make_user("cons_match_inviter")
        friend_pending, _ = PendingInvite.objects.create_pending(
            inviter=friend_inviter, email="consumed@test.local",
        )
        match_pending, _ = PendingInvite.objects.create_pending(
            inviter=match_inviter,
            email="consumed@test.local",
            invite_type="match",
            payload={"format": "BLITZ"},
        )
        user = User.objects.create_user(
            username="cons_newbie", email="consumed@test.local", password=PASSWORD,
        )

        # The match invite only materializes if a match is creatable now —
        # seed the catalog so the send-time gate passes.
        with mock_golden_seed(make_golden_seed_selection()):
            consumed = PendingInvite.objects.consume_for_user(user)

        self.assertEqual(consumed, 2)
        # Friend edge in both directions (symmetric M2M).
        self.assertTrue(friend_inviter.is_friend(user))
        self.assertTrue(user.is_friend(friend_inviter))
        self.assertTrue(match_inviter.is_friend(user))
        self.assertTrue(user.is_friend(match_inviter))
        # Match pending also materialized a real Invite with its payload.
        invites = Invite.objects.filter(
            type="match", sender=match_inviter, player=user,
        )
        self.assertEqual(invites.count(), 1)
        invite = invites.get()
        self.assertEqual(invite.state, "sent")
        self.assertEqual(invite.payload.get("format"), "BLITZ")
        # The friend-type pending must NOT materialize an Invite.
        self.assertFalse(
            Invite.objects.filter(sender=friend_inviter, player=user).exists()
        )
        # Both rows stamped consumed.
        friend_pending.refresh_from_db()
        match_pending.refresh_from_db()
        self.assertIsNotNone(friend_pending.consumed_at)
        self.assertIsNotNone(match_pending.consumed_at)
        # Metric fired once per consumed invite.
        self.assertEqual(
            ProductEvent.objects.filter(
                user=user, name="signup_invite_consumed"
            ).count(),
            2,
        )

    def test_match_invite_skipped_when_uncreatable_friendship_kept(self):
        """At signup the original window may no longer hold fixtures — the
        match invite is skipped (no dead invite) but the friendship still
        lands and the pending row is stamped consumed."""
        match_inviter = make_user("skip_match_inviter")
        match_pending, _ = PendingInvite.objects.create_pending(
            inviter=match_inviter,
            email="skip@test.local",
            invite_type="match",
            payload={"format": "BLITZ"},
        )
        user = User.objects.create_user(
            username="skip_newbie", email="skip@test.local", password=PASSWORD,
        )

        # Empty catalog → the creatability choke-point raises → invite skipped.
        empty_client = MagicMock()
        empty_client.list_events.return_value = {"items": []}
        with patch(
            "core.event.providers.aggregator_client.AggrigatorClient",
            return_value=empty_client,
        ):
            consumed = PendingInvite.objects.consume_for_user(user)

        self.assertEqual(consumed, 1)
        self.assertTrue(match_inviter.is_friend(user))
        self.assertFalse(
            Invite.objects.filter(
                type="match", sender=match_inviter, player=user
            ).exists()
        )
        match_pending.refresh_from_db()
        self.assertIsNotNone(match_pending.consumed_at)

    def test_second_call_consumes_nothing(self):
        inviter = make_user("cons_twice_inviter")
        PendingInvite.objects.create_pending(
            inviter=inviter, email="twice@test.local",
        )
        user = User.objects.create_user(
            username="cons_twice", email="twice@test.local", password=PASSWORD,
        )

        self.assertEqual(PendingInvite.objects.consume_for_user(user), 1)
        self.assertEqual(PendingInvite.objects.consume_for_user(user), 0)

    def test_self_invite_is_skipped_but_stamped(self):
        loner = make_user("cons_self")
        pending, _ = PendingInvite.objects.create_pending(
            inviter=loner, email=loner.email,
        )

        consumed = PendingInvite.objects.consume_for_user(loner)

        self.assertEqual(consumed, 0)
        pending.refresh_from_db()
        self.assertIsNotNone(pending.consumed_at)
        self.assertFalse(loner.get_friends().exists())


@override_settings(USE_AGGRIGATOR=False)
class RegisterFormWaitlistBypassTests(TestCase):
    def test_pending_invite_bypasses_waitlist_gate(self):
        inviter = make_user("form_inviter")
        PendingInvite.objects.create_pending(
            inviter=inviter, email="bypass@test.local",
        )

        form = RegisterForm(register_data("bypass@test.local", username="bypasser"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_without_invite_or_waitlist_approval_email_is_rejected(self):
        form = RegisterForm(register_data("nobody@test.local", username="nobody"))

        self.assertFalse(form.is_valid())
        self.assertIn(
            "You have not been approved to register", form.errors.get("email", []),
        )


@override_settings(USE_AGGRIGATOR=False)
class RegisterViewInviteFlowTests(TestCase):
    URL = reverse("core-auth:register")

    def setUp(self):
        self.inviter = make_user("view_inviter")
        self.pending, _ = PendingInvite.objects.create_pending(
            inviter=self.inviter,
            email="invited@test.local",
            invite_type="match",
            payload={"format": "BLITZ"},
        )

    def test_get_with_valid_token_sets_session_and_prefills_email(self):
        # token is a signed value that re-encodes the current timestamp on every
        # access, so capture it once rather than regenerating it for the assert.
        token = self.pending.token
        resp = self.client.get(self.URL, {"invite": token}, secure=True)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.client.session.get(PENDING_INVITE_SESSION_KEY), token,
        )
        self.assertContains(resp, "invited@test.local")

    def test_get_with_invalid_token_warns_without_crashing(self):
        resp = self.client.get(self.URL, {"invite": "garbage-token"}, secure=True)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(PENDING_INVITE_SESSION_KEY, self.client.session)

    @patch("core.auth.models.email.send_activation_email")
    def test_post_registers_consumes_and_leaves_match_invite_waiting(
        self, mock_send,
    ):
        self.client.get(self.URL, {"invite": self.pending.token}, secure=True)

        # Seed the catalog so the match invite passes the send-time
        # creatability gate during consume-on-register.
        with mock_golden_seed(make_golden_seed_selection()):
            resp = self.client.post(
                self.URL,
                register_data("invited@test.local", username="invitee"),
                secure=True,
                REMOTE_ADDR="10.0.0.11",
            )

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("core-auth:activation-email"))
        user = User.objects.get(email="invited@test.local")
        mock_send.assert_called_once()
        self.pending.refresh_from_db()
        self.assertIsNotNone(self.pending.consumed_at)
        self.assertTrue(self.inviter.is_friend(user))
        self.assertTrue(user.is_friend(self.inviter))
        invite = Invite.objects.get(type="match", sender=self.inviter, player=user)
        self.assertEqual(invite.state, "sent")
        self.assertEqual(invite.payload.get("format"), "BLITZ")
        self.assertTrue(
            ProductEvent.objects.filter(
                user=user, name="signup_invite_consumed"
            ).exists()
        )


@override_settings(USE_AGGRIGATOR=False)
class RegisterViewReferralTests(TestCase):
    URL = reverse("core-auth:register")

    def setUp(self):
        self.referrer = make_user("referrer")
        self.assertTrue(self.referrer.friend_code)  # assigned on save()

    @patch("core.auth.models.email.send_activation_email")
    def test_referral_with_waitlist_approval_creates_friend_edge(self, mock_send):
        WaitlistEntry.objects.create(
            email="referred@test.local",
            full_name="Referred Person",
            admin_granted_access=True,
        )

        resp = self.client.get(
            self.URL, {"ref": self.referrer.friend_code}, secure=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            self.client.session.get(REFERRAL_SESSION_KEY),
            self.referrer.friend_code,
        )

        resp = self.client.post(
            self.URL,
            register_data("referred@test.local", username="referred"),
            secure=True,
            REMOTE_ADDR="10.0.0.21",
        )

        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(email="referred@test.local")
        self.assertTrue(self.referrer.is_friend(user))
        self.assertTrue(user.is_friend(self.referrer))
        self.assertTrue(
            ProductEvent.objects.filter(user=user, name="referral_signup").exists()
        )

    def test_referral_does_not_bypass_waitlist(self):
        self.client.get(self.URL, {"ref": self.referrer.friend_code}, secure=True)

        resp = self.client.post(
            self.URL,
            register_data("unapproved@test.local", username="unapproved"),
            secure=True,
            REMOTE_ADDR="10.0.0.22",
        )

        # Form re-rendered with errors; no account row.
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            User.objects.filter(email="unapproved@test.local").exists()
        )
