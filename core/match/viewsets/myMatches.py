from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.match.serializers.match import MatchSerializer
from core.match.models.match import Match
from core.match.pagination.pagination import MatchPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q
from django.utils import timezone
from datetime import datetime

class MatchViewSet(AbstractViewSet):
    http_method_names = ('get', 'post', 'patch')
    authentication_classes = (JWTAuthentication,)
    filter_backends = [OrderingFilter, SearchFilter]
    permission_classes = (IsAuthenticated,)
    serializer_class = MatchSerializer
    queryset = Match.objects.all()
    ordering = ['-created']
    pagination_class = MatchPagination  # Use the custom pagination class
    search_fields = ['player_1__username', 'player_2__username', 'match_state', 'match_type']  # Add more fields if needed

    def get_queryset(self):
        user = self.request.user
        queryset = Match.objects.filter(
            Q(player_1=user) | Q(player_2=user)
        ).distinct()

        # Define the allowed parameters and default values
        match_state = self.request.query_params.get('match_state', None)
        search_query = self.request.query_params.get('search', None)
        start_date_start = self.request.query_params.get('start_date_start', None)
        start_date_end = self.request.query_params.get('start_date_end', None)

        if search_query:
            queryset = queryset.filter(
                Q(player_1__username__icontains=search_query) |
                Q(player_2__username__icontains=search_query) |
                Q(match_state__icontains=search_query) |
                Q(match_type__icontains=search_query)
            )

        if start_date_start:
            try:
                start_date = datetime.strptime(start_date_start, '%Y-%m-%d')
                start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
                queryset = queryset.filter(start_date__gte=start_date)
            except ValueError:
                pass  # Handle the error or log it

        if start_date_end:
            try:
                end_date = datetime.strptime(start_date_end, '%Y-%m-%d')
                end_date = timezone.make_aware(end_date, timezone.get_current_timezone())
                queryset = queryset.filter(start_date__lte=end_date)
            except ValueError:
                pass  # Handle the error or log it

        if match_state:
            queryset = queryset.filter(match_state=match_state)

        return queryset

    def get_object(self):
        obj = Match.objects.get(pk=self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    def list(self, request, *args, **kwargs):
        if 'user' in request.path:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        player_1 = request.user
        match = Match.objects.create_match(player_1)
        serializer = self.get_serializer(match)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        from core.game.models.game import GoldenGameUnavailable
        player_2 = request.user
        match = Match.objects.get_object_by_id(kwargs['pk'])
        try:
            match = Match.objects.accept_match(match, player_2)
        except GoldenGameUnavailable as exc:
            return Response({'detail': str(exc)}, status=400)
        serializer = self.get_serializer(match)
        return Response(serializer.data)
