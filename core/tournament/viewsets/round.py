from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.tournament.models.tournament import Player, Round
from core.tournament.serializers.tournament import RoundSerializer


class RoundViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    http_method_names = ('get', 'patch')
    serializer_class = RoundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Allow all rounds to be queried
        return Round.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        user = self.request.user
        players = Player.objects.filter(player=user)
        queryset = Round.objects.filter(player_1__in=players) | Round.objects.filter(player_2__in=players)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='tournament/(?P<tournament_id>[^/.]+)')
    def tournament_rounds(self, request, tournament_id=None):
        rounds = Round.objects.filter(tournament__id=tournament_id)
        serializer = self.get_serializer(rounds, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='user-rounds')
    def user_rounds(self, request):
        user = self.request.user
        players = Player.objects.filter(player=user)
        rounds = Round.objects.filter(player_1__in=players) | Round.objects.filter(player_2__in=players)
        serializer = self.get_serializer(rounds, many=True)
        return Response(serializer.data)
