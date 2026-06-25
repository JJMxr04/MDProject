"""Send-time creatability gate.

A regular match invite must not email the recipient unless a match in that
format could actually be built right now. This closes the user-reported bug
where an invite email went out but accepting it was blocked at accept time by
``FixtureUnavailable`` / ``GoldenGameUnavailable`` — stranding the recipient
with a challenge they could never honour.
"""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from procrastinate.contrib.django.models import ProcrastinateJob

from core.game.models.game import FixtureUnavailable
from core.mail.models import Invite
from core.match.models import Match
from core.match.tests.factories import (
    make_golden_seed_selection,
    make_user,
    mock_golden_seed,
)


def _email_jobs():
    return ProcrastinateJob.objects.filter(task_name="core.mail.send_email")


def _empty_catalog():
    """Force the aggregator events listing to be empty so the creatability
    gate raises deterministically — without this the tests depend on whether
    the local aggregator dev server happens to be up."""
    client = MagicMock()
    client.list_events.return_value = {"items": []}
    return patch(
        "core.event.providers.aggregator_client.AggrigatorClient",
        return_value=client,
    )


@override_settings(USE_AGGRIGATOR=False)
class CreateInviteChokepointTests(TestCase):
    """The creatability gate lives in the single choke-point
    ``InviteManager.create_invite`` — every match-invite path inherits it."""

    def test_match_invite_gated_at_manager(self):
        sender = make_user("cm_s")
        player = make_user("cm_p")
        before = _email_jobs().count()

        with _empty_catalog(), self.assertRaises(FixtureUnavailable):
            Invite.objects.create_invite(
                obj_id=None, player=player, invite_type="match", sender=sender,
                payload={"format": "CLASSIC"},
            )

        # Nothing written, nothing emailed.
        self.assertFalse(
            Invite.objects.filter(sender=sender, player=player).exists()
        )
        self.assertEqual(_email_jobs().count(), before)

    def test_match_invite_succeeds_when_catalog_can_seed(self):
        sender = make_user("cm_s2")
        player = make_user("cm_p2")
        with mock_golden_seed(make_golden_seed_selection()):
            invite = Invite.objects.create_invite(
                obj_id=None, player=player, invite_type="match", sender=sender,
                payload={"format": "CLASSIC"},
            )
        self.assertEqual(invite.state, "sent")

    def test_duel_invite_skips_match_gate(self):
        """Duels validate their own event chain upstream — an empty fixture
        catalog must not block a duel invite."""
        sender = make_user("cd_s")
        player = make_user("cd_p")
        invite = Invite.objects.create_invite(
            obj_id=None, player=player, invite_type="match", sender=sender,
            payload={"duel": True, "event_label": "x"},
            expires_at=timezone.now() + timedelta(hours=2),
        )
        self.assertEqual(invite.state, "sent")

    def test_friend_invite_not_gated(self):
        sender = make_user("cf_s")
        player = make_user("cf_p")
        invite = Invite.objects.create_invite(
            obj_id=None, player=player, invite_type="friend", sender=sender,
        )
        self.assertEqual(invite.state, "sent")


@override_settings(USE_AGGRIGATOR=False)
class AssertMatchCreatableTests(TestCase):
    def test_raises_when_no_fixtures_available(self):
        with _empty_catalog(), self.assertRaises(FixtureUnavailable):
            Match.objects.assert_match_creatable("CLASSIC")

    def test_passes_when_catalog_can_seed(self):
        sel = make_golden_seed_selection()
        with mock_golden_seed(sel):
            # Should not raise — fixtures + a golden seed are available.
            Match.objects.assert_match_creatable("CLASSIC")


@override_settings(USE_AGGRIGATOR=False)
class InviteByEmailGateTests(TestCase):
    def test_match_invite_to_existing_user_blocked_when_uncreatable(self):
        sender = make_user("gate_s")
        target = make_user("gate_t")
        self.client.force_login(sender)
        before = _email_jobs().count()

        with _empty_catalog():
            resp = self.client.post(
                reverse("core-portal:invite-by-email"),
                json.dumps({
                    "email": target.email, "invite_type": "match",
                    "format": "CLASSIC",
                }),
                content_type="application/json",
                secure=True,
            )

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            Invite.objects.filter(
                sender=sender, player=target, type="match"
            ).exists()
        )
        self.assertEqual(_email_jobs().count(), before)

    def test_friend_invite_to_existing_user_not_gated(self):
        sender = make_user("gatef_s")
        target = make_user("gatef_t")
        self.client.force_login(sender)

        resp = self.client.post(
            reverse("core-portal:invite-by-email"),
            json.dumps({"email": target.email, "invite_type": "friend"}),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            Invite.objects.filter(
                sender=sender, player=target, type="friend"
            ).exists()
        )
