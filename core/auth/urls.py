from django.urls import path
from django.contrib.auth import views as auth_views
from .views.register_view import RegisterView
from .views.waitlist_view import WaitListView
from .views import waitlist_view

app_name = 'core-auth'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='authorization/login.html'), name='login'),
    path('register/', RegisterView.as_view(template_name='authorization/register.html'), name='register'),
    path('waitlist/', WaitListView.as_view(template_name='authorization/waitlist.html'), name='waitlist-list'),
    path('waitlist/thank-you/', waitlist_view.WaitlistThankYouView, name='waitlist-list-thank-you'),
]
