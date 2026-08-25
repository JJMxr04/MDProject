from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from core.api.auth import V1_AUTHENTICATION_CLASSES
from core.event.models import Event
from core.event.odds.service import get_event_odds
from core.event.serializers.event import EventSerializer, EventWithMarketsSerializer

SPORT_ID_BY_SLUG = {
    "soccer": 1,
    "basketball": 2,
    "american_football": 63,
    "ice_hockey": 4,
}


class EventPageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def _parse_bool(value):
    if value is None:
        return None
    return str(value).lower() in ("1", "true", "yes")


class EventListView(APIView):
    # Was AllowAny (anonymous). Locked to authenticated callers (portal
    # session cookie or future JWT) + the `user` throttle scope. No anonymous
    # caller exists in the codebase (audited).
    authentication_classes = V1_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    pagination_class = EventPageNumberPagination

    def get(self, request):
        sport_slug = request.query_params.get("sport")
        if sport_slug not in SPORT_ID_BY_SLUG:
            allowed = ", ".join(sorted(SPORT_ID_BY_SLUG))
            return Response(
                {"detail": f"sport is required and must be one of: {allowed}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = Event.objects.filter(sport_id=SPORT_ID_BY_SLUG[sport_slug])

        live = _parse_bool(request.query_params.get("live"))
        if live is True:
            qs = qs.filter(status_type="inprogress")
        elif live is False:
            qs = qs.exclude(status_type="inprogress")

        date_str = request.query_params.get("date")
        if date_str:
            try:
                day = datetime.fromisoformat(date_str).date()
            except ValueError:
                return Response({"detail": "date must be YYYY-MM-DD"}, status=400)
            start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
            end = start + timedelta(days=1)
            qs = qs.filter(start_time__gte=start, start_time__lt=end)
        else:
            now = timezone.now()
            qs = qs.filter(start_time__gte=now - timedelta(hours=3), start_time__lt=now + timedelta(days=3))

        # Filter on Event.league_id directly. The previous filter referenced
        # ``unique_tournament_id``, a SofaScore-era attribute that was never
        # defined on the SGO-shaped Event model — every ?league= request
        # raised.
        league = request.query_params.get("league")
        if league:
            qs = qs.filter(league_id=league)

        qs = qs.select_related(
            "home_team", "home_team__logo",
            "away_team", "away_team__logo",
            "sport",
        ).order_by("start_time")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        include_markets = request.query_params.get("include") == "markets"
        if include_markets:
            serializer = EventWithMarketsSerializer(page, many=True, context={"top_only": True})
        else:
            serializer = EventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class EventDetailView(APIView):
    # Locked down (see EventListView).
    authentication_classes = V1_AUTHENTICATION_CLASSES
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get(self, request, event_id):
        event = Event.objects.select_related(
            "home_team", "home_team__logo",
            "away_team", "away_team__logo",
            "sport",
        ).filter(pk=event_id).first()
        if event is None:
            return Response({"detail": "event not found"}, status=status.HTTP_404_NOT_FOUND)

        stale = False
        calls_used = 0
        if request.query_params.get("include") == "markets":
            result = get_event_odds(event)
            stale = result.stale
            calls_used = result.calls_this_month
            serializer = EventWithMarketsSerializer(event)
            body = serializer.data
            body["odds_meta"] = {
                "stale": stale,
                "calls_this_month": calls_used,
            }
            return Response(body)

        return Response(EventSerializer(event).data)
