"""Analytics URL surface — score-driven explore + decision dashboard.

Mounted (without a sub-prefix) from ``core.portal.urls`` so paths still
read the same as before (e.g. ``/web/portal/analytics/``).

Routing notes:
- ``/analytics/upcoming/`` and ``/analytics/event/<id>/`` moved to the
  events surface on 2026-05-21 — analytics renders inline there, gated
  by entitlement. URL **names** are preserved as 301-redirect shims so
  any template / email link that resolves them still lands users on the
  right page. Don't add a new view to either of those routes — that
  would silently bypass the redirect.
- Picks / bets / league / team / explore landing all live here, gated
  by ``@require_paid`` at the view layer.

Original landing IA: ``plans/analytics/dashboard_and_data/
01-information-architecture.md``.
"""

from __future__ import annotations

from django.urls import path

from . import views


# No ``app_name`` here — these patterns are mounted *into* the
# ``core-portal`` namespace from ``core/portal/urls.py``. Setting
# ``app_name`` here would either create a nested namespace (breaking
# every ``{% url 'core-portal:analytics-…' %}`` in templates) or be
# silently ignored, depending on how the include() is wired.

urlpatterns = [
    # Disabled 2026-05-22: explore landing, picks, and bets are
    # temporarily off the surface (sidebar + URL) while the analytics
    # IA is in flux. Uncomment to bring them back; nothing else changed
    # on the view side. The bets *action* sub-route is commented too
    # because it has no entry point without the bets list page.
    # path('analytics/', views.analytics_landing, name='analytics-landing'),

    # Redirect shims — see module docstring. Kept active so any inbound
    # link still lands users on the canonical events surface.
    path(
        'analytics/upcoming/',
        views.analytics_upcoming_redirect,
        name='analytics-upcoming',
    ),
    path(
        'analytics/event/<str:event_id>/',
        views.analytics_event_redirect,
        name='analytics-event',
    ),

    # Live analytics views.
    # path('analytics/picks/', views.analytics_picks, name='analytics-picks'),
    # path('analytics/bets/', views.analytics_bets, name='analytics-bets'),
    # path(
    #     'analytics/bets/<str:bet_id>/action/',
    #     views.analytics_bets_action,
    #     name='analytics-bets-action',
    # ),
    path(
        'analytics/league/<str:league_id>/',
        views.analytics_league,
        name='analytics-league',
    ),
    path(
        'analytics/team/<path:team_id>/',
        views.analytics_team,
        name='analytics-team',
    ),
]
