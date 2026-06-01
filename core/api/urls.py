"""v1 URL router — mounted at ``/api/v1/`` (plan 03 — URL shape).

Resource modules in ``core/api/v1/`` register here as they land per page
migration. The reverse namespace is ``api-v1`` (e.g. ``api-v1:ping``).
"""

from django.urls import path

from core.api.v1.ping import PingView

app_name = "api-v1"

urlpatterns = [
    path("_ping/", PingView.as_view(), name="ping"),
]
