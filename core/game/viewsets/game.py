from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.abstract.viewsets import AbstractViewSet
from core.game.models import Game
from core.game.models.game import PickError
from core.game.serializers.game import GameSerializer
from core.match.pagination.pagination import MatchPagination


class GameViewSet(AbstractViewSet):
    http_method_names = ('get', 'post', 'patch')
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = GameSerializer
    queryset = Game.objects.all()
    ordering = ['-created']
    pagination_class = MatchPagination

    def get_object(self):
        obj = Game.objects.get_object_by_id(self.kwargs['pk'])
        self.check_object_permissions(self.request, obj)
        return obj

    def update(self, request, *args, **kwargs):
        player = request.user
        game = self.get_object()
        if game is None:
            raise ValidationError("Game not found")

        try:
            updated = Game.objects.upload_pick(
                current_user=player,
                match=game.match,
                event_id=request.data.get("event") or request.data.get("event_id"),
                selection_id=request.data.get("player_choice"),
            )
        except PickError as exc:
            raise ValidationError(str(exc))

        return Response(
            {"status": "success", "message": "Game choice updated successfully."},
            status=200,
        )
