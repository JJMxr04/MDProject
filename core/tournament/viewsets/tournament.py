from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.tournament.models.tournament import Tournament, Player
from core.tournament.serializers.tournament import TournamentSerializer
from django.utils import timezone
from django.db.models import Q

class TournamentViewSet(viewsets.ModelViewSet):
    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        now = timezone.now()

        # Filter tournaments where the player is associated with the user
        in_progress_tournaments = Tournament.objects.filter(
            Q(player__player=user) & (Q(start_date__lte=now) | Q(state='inprogress') | Q(state='created'))
        ).order_by('start_date')

        completed_tournaments = Tournament.objects.filter(
            Q(player__player=user) & Q(state='completed')
        )

        # Combine the two querysets
        queryset = (in_progress_tournaments | completed_tournaments).distinct()
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        in_progress_tournaments = queryset.filter(state__in=['inprogress', 'created']).order_by('start_date')
        completed_tournaments = queryset.filter(state='completed')

        in_progress_data = self.get_serializer(in_progress_tournaments, many=True).data
        completed_data = self.get_serializer(completed_tournaments, many=True).data

        formatted_data = {
            'inprogress': in_progress_data,
            'completed': completed_data,
        }

        return Response(formatted_data, status=status.HTTP_200_OK)
