from django.contrib.auth import views as auth_views
from django.urls import include, path

from core.auth.views.password_reset import BrandedPasswordResetView
from core.event.urls import urlpatterns as eventUrls
from core.mail.urls.notifications import urlpatterns as notificationUrls
from core.match.urls import urlpatterns as matchUrls
from core.user.urls import urlpatterns as userUrls

from . import views
from .urls_analytics import urlpatterns as analyticsUrls


app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('rules/', views.rules_view, name='portal-rules'),
    path('support/', views.support_view, name='portal-support'),
    path('developer-updates/', views.developer_updates_view, name='portal-developer-updates'),
    path('availability/', views.availability_view, name='portal-availability'),
    # Analytics surface — own file (urls_analytics.py). Mounted without
    # a sub-prefix so /web/portal/analytics/... paths stay unchanged.
    *analyticsUrls,
    path('billing/', include('core.billing.urls')),
    path('event/', include(eventUrls)),
    path('match/', include(matchUrls)),
    path('potd/', include('core.potd.urls')),
    path('leaderboard/', include('core.ranking.urls')),
    path('tournament/', include('core.tournament.urls')),
    path('user/', include(userUrls)),
    path('mail/', include(notificationUrls)),
    path('reset_password/', BrandedPasswordResetView.as_view(), name='reset_password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name='authorization/password-sent.html'), name='password_reset_sent'),
    path('reset/<uid64>/<token>', auth_views.PasswordResetConfirmView.as_view(template_name='authorization/password-reset-form.html'), name='password_reset_confirm'),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name='authorization/password-reset-complete.html'), name='password_reset_complete'),
]
