from django.urls import path
from django.contrib.auth import views as auth_views
from .views.register_view import RegisterView
from .views.waitlist_view import WaitListView
from .views import waitlist_view
from .views.login_view import LoginView
from .views.unsubscribe import unsubscribe_view
from django.contrib.auth import views as auth_views
from core.auth.views.activation_view import ActivateUserView, activate_yoour_account
from core.auth.views import twofa as twofa_views

app_name = 'core-auth'

urlpatterns = [
    # Two-factor (phase 15): enrollment + recovery (login-required) and the
    # login second step (anonymous, gated by a pending-session entry).
    path('2fa/', twofa_views.security_view, name='2fa-security'),
    path('2fa/setup/', twofa_views.setup_view, name='2fa-setup'),
    path('2fa/disable/', twofa_views.disable_view, name='2fa-disable'),
    path('2fa/regenerate/', twofa_views.regenerate_view, name='2fa-regenerate'),
    path('2fa/verify/', twofa_views.verify_view, name='2fa-verify'),
    # path('login/', auth_views.LoginView.as_view(template_name='authorization/login.html'), name='login'),
    path('login/', LoginView.as_view(template_name='authorization/login.html'), name='login'),
    path('register/', RegisterView.as_view(template_name='authorization/register.html'), name='register'),
    path('waitlist/', WaitListView.as_view(template_name='authorization/waitlist.html'), name='waitlist-list'),
    path('waitlist/thank-you/', waitlist_view.WaitlistThankYouView, name='waitlist-list-thank-you'),
    path('activate/<str:token>/', ActivateUserView.as_view(), name='activate'),
    path('activate-your-email', activate_yoour_account, name='activation-email'),
    # Signed-token unsubscribe for engagement emails — works logged-out
    # (linked from every notification email footer; see core.mail.unsubscribe).
    path('unsubscribe/<str:token>/', unsubscribe_view, name='unsubscribe'),

    
]
