from . import views
from django.urls import path, include
from core.event.urls import urlpatterns as eventUrls

app_name = 'core-match'

urlpatterns = [
    path('me/', views.my_match_list_view, name='portal-my-match-list'),
    path('public/', views.public_match_list_view, name='portal-public-match-list'),
    path('public/create/', views.create_public_match_view, name='portal-create-public-match'),
    path('public/accept/<uuid:match_id>/', views.accept_public_match_view, name='portal-accept-public-match'),
    path('public/<uuid:match_id>/', views.public_match_detail_view, name='portal-public-match-detail'),
    path('<uuid:match_id>/', views.my_match_detail_view, name='portal-my-match-detail'),
    path('<uuid:match_id>/upload_pick/', views.upload_pick, name='portal-upload_pick'),
    path('event/<uuid:event_id>/outcomes/', views.event_outcomes, name='portal-match-event-outcomes'),
    path('game/<uuid:game_id>/market/', views.event_markets, name='portal-match-event-market'),
    path('game/<uuid:game_id>/player_2_select_outcome/', views.player_2_select_outcome, name='portal-match-game-player_2_select_outcome'),
    path('<uuid:match_id>/tiebreaker', views.upload_tiebreaker_score, name='portal-upload-tiebreaker-score'),

]
