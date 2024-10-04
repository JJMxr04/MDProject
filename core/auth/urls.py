from django.urls import path
from django.contrib.auth import views as auth_views
from .views.register_view import RegisterView
from .views.waitlist_view import WaitListView
from .views import waitlist_view
from .views.login_view import LoginView
from django.contrib.auth import views as auth_views

app_name = 'core-auth'

urlpatterns = [
    # path('login/', auth_views.LoginView.as_view(template_name='authorization/login.html'), name='login'),
    path('login/', LoginView.as_view(template_name='authorization/login.html'), name='login'),
    path('register/', RegisterView.as_view(template_name='authorization/register.html'), name='register'),
    path('waitlist/', WaitListView.as_view(template_name='authorization/waitlist.html'), name='waitlist-list'),
    path('waitlist/thank-you/', waitlist_view.WaitlistThankYouView, name='waitlist-list-thank-you'),
    path('reset_password/',auth_views.PasswordResetView.as_view(template_name='authorization/password-reset.html'),name='reset_password'),
    path('reset_password_sent/',auth_views.PasswordResetDoneView.as_view(template_name='authorization/password-sent.html'),name='password_reset_sent'),
    path('reset/<uidb64>/<token>',auth_views.PasswordResetConfirmView.as_view(template_name='authorization/password-reset-form.html'),name='password_reset_confirm'),
    path('reset_password_complete/',auth_views.PasswordResetCompleteView.as_view(template_name='authorization/password-completehtml'),name='password_reset_complete'),
]
