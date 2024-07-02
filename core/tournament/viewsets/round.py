from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.tournament.models.tournament import Round, Player
from core.tournament.serializers.tournament import RoundSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication

class RoundViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)  # Note the comma to make it a tuple
    http_method_names = ('get', 'patch')
    serializer_class = RoundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        players = Player.objects.filter(player=user)
        return Round.objects.filter(player_1__in=players, completed=False) | Round.objects.filter(player_2__in=players, completed=False)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
