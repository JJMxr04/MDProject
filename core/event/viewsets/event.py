from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.event.serializers.event import EventSerializer, EventBookmakerSerializer
from core.event.models.event import Event
from core.event.pagination.pagination import EventPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

class EventViewSet(AbstractViewSet):
    http_method_names = ['get']
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [OrderingFilter, SearchFilter]
    queryset = Event.objects.all()
    ordering = ['commence_time']
    search_fields = ['sport_title', 'away_team', 'home_team', 'commence_time', 'created', 'sport_key']
    pagination_class = EventPagination  # Use the custom pagination class

    def get_queryset(self):
        queryset = Event.objects.get_active_events()
        allowed_params = ['sport_key', 'search', 'commence_time_start', 'commence_time_end']  # Define the allowed parameters
        filter_kwargs = {}

        for param in allowed_params:
            value = self.request.query_params.get(param, None)
            if value:
                if param == 'search':
                    # Custom search logic if needed
                    queryset = queryset.filter(
                        Q(sport_title__icontains=value) |
                        Q(away_team__icontains=value) |
                        Q(home_team__icontains=value) |
                        Q(sport_key__icontains=value)
                    )
                elif param == 'commence_time_start':
                    filter_kwargs['commence_time__gte'] = value
                elif param == 'commence_time_end':
                    filter_kwargs['commence_time__lte'] = value
                else:
                    filter_kwargs[param] = value

        queryset = queryset.filter(**filter_kwargs)
        return queryset

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EventBookmakerSerializer
        return EventSerializer

    def get_object(self):
        obj = Event.objects.get_object_by_id(self.kwargs['pk'])
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
