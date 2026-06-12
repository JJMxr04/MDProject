"""``/api/v1/matches/`` — participant-scoped match detail (S-15 family).

Every queryset is filtered to matches where the requester is ``player_1`` or
``player_2``, so a non-participant id 404s before any permission runs (existence
not leaked). ``IsPlayerInMatch`` is declared as a belt-and-braces object check.

Read-only list/detail. The old ``tiebreaker`` action (submit a total guess)
was removed with D-5 #1 — the Golden Game pick IS the tiebreaker now; there
is nothing extra to submit.
"""

from django.db.models import Q
from rest_framework import mixins, viewsets

from core.api.base import V1ViewMixin
from core.api.permissions import IsPlayerInMatch
from core.match.models import Match
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
