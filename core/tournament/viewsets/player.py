from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from core.tournament.models.tournament import Player
from core.tournament.serializers.tournament import PlayerSerializer

class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Player.objects.filter(tournament__owner=user)
