from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.match.serializers.match import MatchSerializer
from core.match.models.match import Match
from core.match.pagination.pagination import MatchPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response


class GameViewSet(AbstractViewSet):
    http_method_names = ('get','post','patch')
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = MatchSerializer
    queryset = Match.objects.all()
    ordering = ['-commence_time']
    # ordering = []
    pagination_class = MatchPagination  # Use the custom pagination class

    def get_queryset(self):
        return Match.objects.filter(completed=False)

    def get_object(self):
        obj = Match.objects.get_object_by_public_id(self.kwargs['pk'])

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

    def create(self):
        player_1 = self.request.user
        return Match.objects.create_match(player_1)