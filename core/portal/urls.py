from django.urls import path, include, re_path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.event.urls import urlpatterns as eventUrls
from core.match.urls import urlpatterns as matchUrls
from core.user.urls import urlpatterns as userUrls
from core.mail.urls.notifications import urlpatterns as notificationUrls
from django.contrib.auth import views as auth_views


app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('rules/', views.rules_view, name='portal-rules'),
    path('availability/', views.availability_view, name='portal-availability'),
    # Analytics — score-driven explore + decision dashboard. Default
    # landing is the league browser (Explore); Tonight / Edge were
    # removed in the 2026-05-19 redesign (see
    # plans/analytics/dashboard_and_data/01-information-architecture.md).
    path('analytics/', views.analytics_landing, name='analytics-landing'),
    path('analytics/upcoming/', views.analytics_upcoming, name='analytics-upcoming'),
    path('analytics/picks/', views.analytics_picks, name='analytics-picks'),
    path('analytics/bets/', views.analytics_bets, name='analytics-bets'),
    path('analytics/bets/<str:bet_id>/action/', views.analytics_bets_action, name='analytics-bets-action'),
    path('analytics/league/<str:league_id>/', views.analytics_league, name='analytics-league'),
    path('analytics/team/<path:team_id>/', views.analytics_team, name='analytics-team'),
    path('analytics/event/<str:event_id>/', views.analytics_event, name='analytics-event'),
    path('billing/', include('core.billing.urls')),
    path('event/', include(eventUrls)), # Ensure this line is correct
    path('match/', include(matchUrls)),
    path('tournament/', include('core.tournament.urls')),
    path('user/', include(userUrls)),
    path('mail/', include(notificationUrls)),
    path('reset_password/',auth_views.PasswordResetView.as_view(template_name='authorization/password-reset.html'),name='reset_password'),
    path('reset_password_sent/',auth_views.PasswordResetDoneView.as_view(template_name='authorization/password-sent.html'),name='password_reset_sent'),
    path('reset/<uid64>/<token>',auth_views.PasswordResetConfirmView.as_view(template_name='authorization/password-reset-form.html'),name='password_reset_confirm'),
    path('reset_password_complete/',auth_views.PasswordResetCompleteView.as_view(template_name='authorization/password-reset-complete.html'),name='password_reset_complete'),

]
