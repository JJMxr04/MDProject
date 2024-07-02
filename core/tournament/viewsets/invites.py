from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.tournament.serializers.tournament import InvitedPlayerSerializer
from core.tournament.models.tournament import Tournament, InvitedPlayer
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.mail.models import Emails

from django.utils import timezone

class InvitedPlayerViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)  # Note the comma to make it a tuple
    http_method_names = ('get', 'patch')  # Limiting allowed methods
    serializer_class = InvitedPlayerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return InvitedPlayer.objects.filter(player=user)

    def update(self, request, *args, **kwargs):
        user = self.request.user
        invited_player = self.get_object()


        if invited_player.state != 'sent':
            return Response({'error': 'Invite is not in sent state.'}, status=status.HTTP_400_BAD_REQUEST)
        tournament = Tournament.objects.get_object_by_id(invited_player.tournament.id)
        success = Tournament.objects.accept_invite(tourney_id=tournament.id, invited_player=invited_player)


        if success:
            # Optionally update the state or other attributes of invited_player here
            InvitedPlayer.objects.accept_invite(invited_player=invited_player)
            # Serialize only necessary fields
            serializer = InvitedPlayerSerializer(instance=invited_player)
            Emails.send_tournament_acceptance_confirmation(user,tournament)
            return Response(serializer.data)
        else:
            return Response({'error': 'Failed to accept invite.'}, status=status.HTTP_400_BAD_REQUEST)

