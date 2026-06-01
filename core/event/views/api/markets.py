from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.api.auth import V1_AUTHENTICATION_CLASSES
from core.event.models import Event, Market
from core.event.odds.service import get_event_odds
from core.event.serializers.market import MarketSerializer


# scope_subject sugar: ?scope_subject=game maps to game-level categories,
# ?scope_subject=team to per-team prop categories. Kept narrow on purpose —
# PROPS_PLAYER is intentionally not enabled in v1.
SCOPE_SUBJECT_SHORTCUT = {
    "game": ["MONEYLINE", "SPREAD", "TOTAL", "PROPS_GAME"],
    "team": ["PROPS_TEAM"],
}


def _csv(request, key):
    raw = request.query_params.get(key)
    return [v for v in (raw.split(",") if raw else []) if v]


class EventMarketsView(APIView):
    # S-3/D4: locked to authenticated callers + `user` throttle (was AllowAny).
    authentication_classes = V1_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, event_id):
        event = Event.objects.filter(pk=event_id).first()
        if event is None:
            return Response({"detail": "event not found"}, status=status.HTTP_404_NOT_FOUND)

        # Trigger on-demand fetch so the DB has something to read from
        result = get_event_odds(event)

        qs = Market.objects.filter(event=event).prefetch_related("selections")

        categories = _csv(request, "category")
        if categories:
            qs = qs.filter(category__in=categories)

        scope_subject = request.query_params.get("scope_subject")
        if scope_subject in SCOPE_SUBJECT_SHORTCUT:
            qs = qs.filter(category__in=SCOPE_SUBJECT_SHORTCUT[scope_subject])

        scopes = _csv(request, "scope")
        if scopes:
            qs = qs.filter(scope__in=scopes)

        market_type = request.query_params.get("type")
        if market_type:
            qs = qs.filter(type=market_type)

        live = request.query_params.get("live")
        if live is not None:
            qs = qs.filter(is_live=str(live).lower() in ("1", "true", "yes"))

        team_id = request.query_params.get("team_id")
        if team_id:
            qs = qs.filter(subject_team_id=team_id)

        settled = request.query_params.get("settled")
        if settled is not None:
            if str(settled).lower() in ("1", "true", "yes"):
                qs = qs.filter(selections__settlement_status__in=["WON", "LOST", "PUSH", "VOID"])
            else:
                qs = qs.filter(selections__settlement_status="PENDING")
            qs = qs.distinct()

        if str(request.query_params.get("winners_only", "")).lower() in ("1", "true", "yes"):
            qs = qs.filter(selections__settlement_status="WON").distinct()

        min_dec = request.query_params.get("min_decimal")
        max_dec = request.query_params.get("max_decimal")
        if min_dec or max_dec:
            try:
                if min_dec:
                    qs = qs.filter(selections__decimal_odds__gte=Decimal(min_dec))
                if max_dec:
                    qs = qs.filter(selections__decimal_odds__lte=Decimal(max_dec))
            except InvalidOperation:
                return Response({"detail": "min_decimal/max_decimal must be numeric"}, status=400)
            qs = qs.distinct()

        qs = qs.order_by("category", "scope", "line")
        return Response({
            "markets": MarketSerializer(qs, many=True).data,
            "odds_meta": {
                "stale": result.stale,
                "calls_this_month": result.calls_this_month,
            },
        })
