from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q
from core.tournament.models.tournament import Tournament
from core.tournament.serializers.tournament import TournamentSerializer
from core.tournament.pagination.pagination import TournamentPagination  # Assuming a custom pagination class
from django.utils import timezone
from datetime import datetime

class TournamentViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    filter_backends = [OrderingFilter, SearchFilter]
    serializer_class = TournamentSerializer
    queryset = Tournament.objects.all()
    ordering = ['start_date']
    search_fields = ['name', 'state', 'start_date']
    pagination_class = TournamentPagination  # Use the custom pagination class

    def get_queryset(self):
        user = self.request.user
        queryset = Tournament.objects.filter(player__player=user).distinct()
        allowed_params = ['state', 'search', 'start_date_start', 'start_date_end']  # Define the allowed parameters
        filter_kwargs = {}

        for param in allowed_params:
            value = self.request.query_params.get(param, None)
            if value:
                if param == 'search':
                    queryset = queryset.filter(
                        Q(name__icontains=value) |
                        Q(state__icontains=value) |
                        Q(start_date__icontains=value)
                    )
                elif param == 'start_date_start':
                    try:
                        start_date = datetime.strptime(value, '%Y-%m-%d')
                        start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
                        filter_kwargs['start_date__gte'] = start_date
                    except ValueError:
                        pass  # Handle the error or log it
                elif param == 'start_date_end':
                    try:
                        end_date = datetime.strptime(value, '%Y-%m-%d')
                        end_date = timezone.make_aware(end_date, timezone.get_current_timezone())
                        filter_kwargs['start_date__lte'] = end_date
                    except ValueError:
                        pass  # Handle the error or log it
                else:
                    filter_kwargs[param] = value

        queryset = queryset.filter(**filter_kwargs)
        return queryset

    def get_object(self):
        obj = Tournament.objects.get(pk=self.kwargs['pk'], player__player=self.request.user)
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
