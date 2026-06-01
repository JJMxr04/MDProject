"""Phase 2: /api/v1/dashboard/stats/ — per-user scoped counts."""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status

from core.api.tests.base import V1APITestCase
from core.mail.models import Invite, Notification
from core.match.models import Match


class DashboardStatsApiTests(V1APITestCase):
    def setUp(self):
        self.alice = self.make_user("alice")
        self.bob = self.make_user("bob")
        self.url = reverse("api-v1:dashboard-stats")

        # alice: 1 active match (vs bob), 1 completed (excluded).
        Match.objects.create(
            player_1=self.alice, player_2=self.bob, match_state="accepted"
        )
        Match.objects.create(
            player_1=self.alice, player_2=self.bob, match_state="completed"
        )
        # alice: 1 pending received invite, plus a non-pending one (excluded).
        Invite.objects.create(player=self.alice, sender=self.bob, type="friend", state="sent")
        Invite.objects.create(player=self.alice, sender=self.bob, type="friend", state="accepted")
        # bob has an invite that must not count toward alice.
        Invite.objects.create(player=self.bob, sender=self.alice, type="friend", state="sent")
        # alice: 2 notifications, bob: 1.
        Notification.objects.create_notification(self.alice, "n1")
        Notification.objects.create_notification(self.alice, "n2")
        Notification.objects.create_notification(self.bob, "n3")

    def test_stats_are_scoped_to_requester(self):
        self.client.force_authenticate(self.alice)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = self.assert_success_envelope(resp)
        self.assertEqual(data["active_matches"], 1)
        self.assertEqual(data["pending_invites"], 1)
        self.assertEqual(data["notifications"], 2)

    def test_other_user_sees_own_counts(self):
        self.client.force_authenticate(self.bob)
        data = self.assert_success_envelope(self.client.get(self.url))
        self.assertEqual(data["active_matches"], 1)
        self.assertEqual(data["pending_invites"], 1)
        self.assertEqual(data["notifications"], 1)

    def test_anonymous_is_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assert_error_envelope(resp, code="not_authenticated")
