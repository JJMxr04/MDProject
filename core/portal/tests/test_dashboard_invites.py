"""The dashboard's pending-invite count reflects only *actionable* invites —
effectively-expired ``sent`` rows (past ``expires_at``, not yet churned by the
nightly cron) must not inflate the badge."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.mail.models import Invite
from core.match.tests.factories import make_user


@override_settings(USE_AGGRIGATOR=False)
class DashboardPendingInviteCountTests(TestCase):
    def test_excludes_effectively_expired_invites(self):
        user = make_user("dpi")
        sender = make_user("dpi_s")
        self.client.force_login(user)

        Invite.objects.create(
            player=user, sender=sender, type="friend", state="sent",
            expires_at=timezone.now() + timedelta(days=1),
        )
        Invite.objects.create(
            player=user, sender=sender, type="friend", state="sent",
            expires_at=timezone.now() - timedelta(hours=1),
        )

        resp = self.client.get(reverse("core-portal:portal-dashboard"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["stats"]["pending_invite_count"], 1)
