from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'core-auth'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='login/login.html'), name='login'),
]
