from django.urls import path, include
from . import views
from .views import UserProfileUpdateView

app_name = 'core-portal'

urlpatterns = [
    path('dashboard/', views.portal_dashboard, name='portal-dashboard'),
    path('event/', include(('core.event.urls', 'core-event'), namespace='core-event'), name='core-event'),
    path('my/tournaments/', views.my_tournaments, name='portal-my-tournaments'),
    path('my/tournaments/<uuid:tournament_id>/', views.my_tournament_detail, name='portal-my-tournament-detail'),
    path('tournament/round/<uuid:round_id>/', views.my_round_detail_view, name='portal-my-tournament-round-detail'),
    path('profile/', UserProfileUpdateView.as_view(), name='profile'),
    path('match/<uuid:match_id>/', views.my_match_detail_view, name='portal-my-match-detail'),
    path('match/<uuid:match_id>/upload_pick/', views.upload_pick, name='portal-upload_pick'),
    path('match/event/<uuid:event_id>/outcomes/', views.event_outcomes, name='portal-match-event-outcomes'),
    path('match/game/<uuid:game_id>/market/', views.event_markets, name='portal-match-event-market'),
    path('match/game/<uuid:game_id>/player_2_select_outcome/', views.player_2_select_outcome, name='portal-match-game-player_2_select_outcome'),
]
