"""v1 URL router — mounted at ``/api/v1/`` (plan 03 — URL shape).

Resource modules in ``core/api/v1/`` register here as they land per page
migration. The reverse namespace is ``api-v1`` (e.g. ``api-v1:ping``).
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from core.api.v1.analytics import EventAnalyticsView
from core.api.v1.availability import AvailabilityView
from core.api.v1.dashboard import DashboardStatsView
from core.api.v1.friends import FriendViewSet
from core.api.v1.matches import MatchViewSet
from core.api.v1.notifications import NotificationViewSet
from core.api.v1.ping import PingView
from core.api.v1.tournaments import TournamentViewSet

app_name = "api-v1"

router = SimpleRouter()
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("friends", FriendViewSet, basename="friends")
router.register("matches", MatchViewSet, basename="matches")
router.register("tournaments", TournamentViewSet, basename="tournaments")

urlpatterns = [
    path("_ping/", PingView.as_view(), name="ping"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("availability/", AvailabilityView.as_view(), name="availability"),
    path(
        "analytics/events/<str:event_id>/",
        EventAnalyticsView.as_view(),
        name="analytics-event",
    ),
    *router.urls,
]
