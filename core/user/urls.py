from .views import UserProfileUpdateView
from django.urls import path, include


app_name = 'core-portal'

urlpatterns = [
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
]
