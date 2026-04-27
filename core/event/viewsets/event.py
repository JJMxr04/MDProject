from django.db.models import Q
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.abstract.viewsets import AbstractViewSet
from core.event.models.event import Event
from core.event.pagination.pagination import EventPagination
from core.event.serializers.event import EventSerializer, EventWithMarketsSerializer


class EventViewSet(AbstractViewSet):
    http_method_names = ["get"]
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [OrderingFilter, SearchFilter]
    queryset = Event.objects.all()
    ordering = ["start_time"]
    search_fields = [
        "season_label",
        "home_team__name_long",
        "away_team__name_long",
    ]
    pagination_class = EventPagination

    def get_queryset(self):
        queryset = Event.objects.active()
        allowed_params = [
            "sport_id",
            "league_id",
            "search",
            "start_time_start",
            "start_time_end",
        ]
        filter_kwargs = {}

        for param in allowed_params:
            value = self.request.query_params.get(param, None)
            if value is None:
                continue
            if param == "search":
                queryset = queryset.filter(
                    Q(season_label__icontains=value)
                    | Q(home_team__name_long__icontains=value)
                    | Q(away_team__name_long__icontains=value)
                )
            elif param == "start_time_start":
                filter_kwargs["start_time__gte"] = value
            elif param == "start_time_end":
                filter_kwargs["start_time__lte"] = value
            else:
                filter_kwargs[param] = value

        return queryset.filter(**filter_kwargs)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EventWithMarketsSerializer
        return EventSerializer

    def get_object(self):
        obj = Event.objects.get_by_public_id(self.kwargs["pk"])
        if obj is None:
            obj = Event.objects.filter(pk=self.kwargs["pk"]).first()
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
