from django.urls import include, path

from core.event.urls import urlpatterns as eventUrls

from . import views

app_name = 'core-match'

urlpatterns = [
    path('me/', views.my_match_list_view, name='portal-my-match-list'),
    path('public/', views.public_match_list_view, name='portal-public-match-list'),
    path('public/create/', views.create_public_match_view, name='portal-create-public-match'),
    path('public/accept/<uuid:match_id>/', views.accept_public_match_view, name='portal-accept-public-match'),
    path('public/<uuid:match_id>/', views.public_match_detail_view, name='portal-public-match-detail'),
    path('<uuid:match_id>/', views.my_match_detail_view, name='portal-my-match-detail'),
    path('<uuid:match_id>/upload_pick/', views.upload_pick, name='portal-upload_pick'),
    # SGO eventIDs are alphanumeric strings; ``<str:>`` (was ``<int:>``).
    path('event/<str:event_id>/outcomes/', views.event_outcomes, name='portal-match-event-outcomes'),
    path('<uuid:match_id>/available_events/',
         views.available_events_for_match,
         name='portal-available-events-for-match'),
    path('game/<uuid:game_id>/market/', views.event_markets, name='portal-match-event-market'),
    path('<uuid:match_id>/game/<uuid:game_id>/market/', views.event_markets, name='portal-match-event-market'),
    path('game/<uuid:game_id>/player_2_select_outcome/', views.player_2_select_outcome, name='portal-match-game-player_2_select_outcome'),
    # Unified pick endpoint for slots whose market is pre-locked (Golden Game).
    # Either player can hit it; the manager routes owner_outcome vs
    # player_2_outcome based on which side of the match they're on.
    path('game/<uuid:game_id>/pick_locked/', views.pick_on_locked_slot, name='portal-match-game-pick-locked'),
    # Pre-submit fixture-availability check for the create-match UI.
    path('availability/', views.match_availability_view, name='portal-match-availability'),
    # Rematch: pre-filled same-format invite, roles swapped.
    path('<uuid:match_id>/rematch/', views.rematch_view, name='portal-match-rematch'),
    # Duel: send a single-game opposite-side challenge.
    path('duels/', views.duels_page_view, name='portal-duels'),
    path('duel/events/', views.duel_events_view, name='portal-match-duel-events'),
    path('duel/send/', views.send_duel_view, name='portal-match-duel-send'),

]
