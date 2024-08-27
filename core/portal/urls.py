from django.urls import path
from . import views
from .views import UserProfileUpdateView

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),  # Corrected path
    path('blog/upcoming-events/', views.upcoming_events_list, name='portal-upcoming-events'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),

]
