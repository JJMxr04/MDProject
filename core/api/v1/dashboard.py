"""``/api/v1/dashboard/stats/`` — per-user scoped counts.

Read-only summary for the requester: active matches, pending received invites,
and notification count. Every count is filtered to ``request.user``; no
aggregator calls.
"""

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.base import V1ViewMixin
from core.mail.models import Invite, Notification
from core.match.models import Match


class DashboardStatsView(V1ViewMixin, APIView):
    pagination_class = None

    def get(self, request):
        user = request.user
        active_matches = (
            Match.objects.filter(Q(player_1=user) | Q(player_2=user))
            .exclude(match_state="completed")
            .count()
        )
        pending_invites = Invite.objects.filter(player=user, state="sent").count()
        notifications = Notification.objects.unread(user).count()
        return Response(
            {
                "active_matches": active_matches,
                "pending_invites": pending_invites,
                "notifications": notifications,
            }
        )
