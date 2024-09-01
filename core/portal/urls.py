from django.urls import path
from . import views
from .views import UserProfileUpdateView

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('blog/upcoming-events/', views.upcoming_events_list, name='portal-upcoming-events'),
    path('blog/upcoming-events/<uuid:event_id>/', views.upcoming_event_detail, name='portal-upcoming-events-detail'),
    path('my/tournaments/', views.my_tournaments, name='portal-my-tournaments'),
    path('my/tournaments/<uuid:tournament_id>/', views.my_tournament_detail, name='portal-my-tournament-detail'),
    path('tournament/round/<uuid:round_id>/', views.my_round_detail_view, name='portal-my-tournament-round-detail'),
    path('profile/', UserProfileUpdateView, name='profile'),
    path('match/<uuid:match_id>//', views.my_match_detail_view, name='portal-my-match-detail'),
]
