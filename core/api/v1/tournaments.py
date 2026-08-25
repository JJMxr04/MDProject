"""``/api/v1/tournaments/`` — participant-scoped tournament list/detail.

Every queryset is filtered to tournaments the requester is enrolled in
(``players__player``), so a non-participant id 404s before any permission runs.
``IsParticipant`` is declared as a belt-and-braces object check. The nested
``rounds`` action is scoped to the parent tournament, so only its participants
can read its bracket.
"""

from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api.base import V1ViewMixin
from core.api.permissions import IsParticipant
from core.tournament.models.tournament import Round, Tournament
from core.tournament.serializers.tournament_v1 import (
    RoundV1Serializer,
    TournamentV1Serializer,
)


class TournamentViewSet(
    V1ViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TournamentV1Serializer
    permission_classes = V1ViewMixin.permission_classes + [IsParticipant]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Tournament.objects.none()
        return (
            Tournament.objects.filter(player__player=user)
            .distinct()
            .order_by("-start_date")
        )

    @action(detail=True, methods=["get"])
    def rounds(self, request, *args, **kwargs):
        """Bracket rounds for a tournament the requester is enrolled in."""
        tournament = self.get_object()  # 404 for a non-participant (scoped qs)
        qs = (
            Round.objects.filter(tournament=tournament)
            .select_related("player_1__player", "player_2__player", "winner__player")
            .order_by("level_num")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = RoundV1Serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(RoundV1Serializer(qs, many=True).data)
