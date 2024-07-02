from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.tournament.serializers.tournament import InvitedPlayerSerializer
from core.tournament.models.tournament import Tournament, InvitedPlayer
from rest_framework_simplejwt.authentication import JWTAuthentication

from datetime import datetime

class InvitedPlayerViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)  # Note the comma to make it a tuple
    http_method_names = ('get', 'patch')  # Limiting allowed methods
    serializer_class = InvitedPlayerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return InvitedPlayer.objects.filter(player=user)

    def update(self, request, *args, **kwargs):
        invited_player = self.get_object()


        if invited_player.state != 'sent':
            return Response({'error': 'Invite is not in sent state.'}, status=status.HTTP_400_BAD_REQUEST)

        success = Tournament.objects.accept_invite(tourney_id=invited_player.tournament.id, invited_player=invited_player)

        if success:
            # Optionally update the state or other attributes of invited_player here
            invited_player.state = 'accepted'

            invited_player.accepted = True
            invited_player.accepted_date = datetime.now()
            invited_player.save()
            # Serialize only necessary fields
            serializer = InvitedPlayerSerializer(instance=invited_player)
            return Response(serializer.data)
        else:
            return Response({'error': 'Failed to accept invite.'}, status=status.HTTP_400_BAD_REQUEST)

