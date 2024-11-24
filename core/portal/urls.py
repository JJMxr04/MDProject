from django.urls import path, include, re_path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.event.urls import urlpatterns as eventUrls
from core.match.urls import urlpatterns as matchUrls
from core.tournament.urls import urlpatterns as tournamentUrls
from core.user.urls import urlpatterns as userUrls
from core.mail.urls.notifications import urlpatterns as notificationUrls
from core.blog.urls import urlpatterns as blogUrls
from core.payments.urls import urlpatterns as paymentUrls
from django.contrib.auth import views as auth_views


app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('event/', include(eventUrls)), # Ensure this line is correct
    path('match/', include(matchUrls)),
    path('tournament/', include(tournamentUrls)),
    path('user/', include(userUrls)),
    path('mail/', include(notificationUrls)),
    # path('blog/', include(blogUrls)),
    # path('payments/', include(paymentUrls)),
    path('reset_password/',auth_views.PasswordResetView.as_view(template_name='authorization/password-reset.html'),name='reset_password'),
    path('reset_password_sent/',auth_views.PasswordResetDoneView.as_view(template_name='authorization/password-sent.html'),name='password_reset_sent'),
    path('reset/<uid64>/<token>',auth_views.PasswordResetConfirmView.as_view(template_name='authorization/password-reset-form.html'),name='password_reset_confirm'),
    path('reset_password_complete/',auth_views.PasswordResetCompleteView.as_view(template_name='authorization/password-completehtml'),name='password_reset_complete'),

]
