"""``/api/v1/matches/`` — participant-scoped match detail (S-15 family).

Every queryset is filtered to matches where the requester is ``player_1`` or
``player_2``, so a non-participant id 404s before any permission runs (existence
not leaked). ``IsPlayerInMatch`` is declared as a belt-and-braces object check.

Exposes a read list/detail plus the ``tiebreaker`` player action (submit a
tiebreaker total) — the same two-sided gate the ``player_in_match_required``
decorator enforces on the legacy view.
"""

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api.base import V1ViewMixin
from core.api.permissions import IsPlayerInMatch
from core.match.models import Match, TieBreaker
from core.match.serializers.match_v1 import MatchV1Serializer


class MatchViewSet(
    V1ViewMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = MatchV1Serializer
    permission_classes = V1ViewMixin.permission_classes + [IsPlayerInMatch]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Match.objects.none()
        qs = (
            Match.objects.filter(Q(player_1=user) | Q(player_2=user))
            .select_related("player_1", "player_2", "winner")
            .order_by("-start_date")
        )
        # Optional ``?state=`` filter (CSV of match_state values). The
        # portal's "Live matches" island passes ``state=accepted`` so
        # completed matches don't show up as live.
        state = (self.request.query_params.get("state") or "").strip()
        if state:
            states = [s.strip() for s in state.split(",") if s.strip()]
            qs = qs.filter(match_state__in=states)
        return qs

    @action(detail=True, methods=["post"])
    def tiebreaker(self, request, *args, **kwargs):
        """Submit this requester's tiebreaker total for the match."""
        match = self.get_object()  # 404 for a non-participant (scoped qs)

        if match.match_state == "completed":
            return Response(
                {"detail": "Match already completed."},
                status=status.HTTP_409_CONFLICT,
            )
        if match.tiebreaker is None or match.tiebreaker.golden_game is None:
            return Response(
                {"detail": "Match has no tiebreaker."},
                status=status.HTTP_409_CONFLICT,
            )

        total = request.data.get("tiebreaker_score")
        if total is None:
            return Response(
                {"detail": "tiebreaker_score is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            total = int(total)
        except (TypeError, ValueError):
            return Response(
                {"detail": "tiebreaker_score must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        golden = match.tiebreaker.golden_game
        if request.user == golden.owner:
            TieBreaker.objects.set_owner_total(tiebreaker=match.tiebreaker, total=total)
        elif request.user == golden.player_2:
            TieBreaker.objects.set_player_2_total(
                tiebreaker=match.tiebreaker, total=total
            )
        else:
            # Participant of the match but not a side of the golden game.
            return Response(
                {"detail": "You are not a player in this tiebreaker."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
