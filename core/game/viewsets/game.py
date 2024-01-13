from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.game.serializers.game import GameSerializer
from core.game.models.game import Game
from core.match.pagination.pagination import MatchPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response


class GameViewSet(AbstractViewSet):
    http_method_names = ('get','post','patch')
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = GameSerializer
    queryset = Game.objects.all()
    ordering = ['-created']
    # ordering = []
    pagination_class = MatchPagination  # Use the custom pagination class



    def get_object(self):
        obj = Game.objects.get_object_by_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)

        return obj

    def update(self, request, *args, **kwargs):
        player = request.user
        print(kwargs['pk'])
        game = Game.objects.update_by_id(kwargs['pk'], player,request.data)[1]
        print(game)
        serializer = self.get_serializer(game)
        return Response(serializer.data)
