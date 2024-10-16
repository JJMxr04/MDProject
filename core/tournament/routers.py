from django.urls import path, include
from rest_framework import routers
from core.tournament.viewsets.tournament import TournamentViewSet
from core.tournament.viewsets.round import RoundViewSet
from core.tournament.viewsets.invites import InviteViewSet
from core.tournament.viewsets.player import PlayerViewSet

router = routers.SimpleRouter()
router.register(r'rounds', RoundViewSet, basename='round')
router.register(r'players', PlayerViewSet, basename='player')
router.register(r'tournaments', TournamentViewSet, basename='tournament')
router.register(r'invited-players', InviteViewSet, basename='Invite')

urlpatterns = [
    path('', include(router.urls)),
    path('tournaments/<uuid:pk>/', TournamentViewSet.as_view({'get': 'retrieve'}), name='tournament-detail'),
    path('invited-players/<uuid:pk>/', InviteViewSet.as_view({'get': 'retrieve', 'patch': 'update'}), name='invited-player-detail'),
    path('rounds/<uuid:pk>/', RoundViewSet.as_view({'get': 'retrieve', 'patch': 'update'}), name='round-detail'),
    path('rounds/tournament/<uuid:tournament_id>/', RoundViewSet.as_view({'get': 'tournament_rounds'}), name='tournament-rounds'),
    path('rounds/user-rounds/', RoundViewSet.as_view({'get': 'user_rounds'}), name='user-rounds'),
]
