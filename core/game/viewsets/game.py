from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.game.serializers.game import GameSerializer, ChoiceSerializer
from core.game.models import Game
from core.match.pagination.pagination import MatchPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError


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

        # Initialize and validate ChoiceSerializer
        choice_serializer = ChoiceSerializer(data=request.data)
        if choice_serializer.is_valid(raise_exception=True):
            validated_data = choice_serializer.validated_data

            # Update the game instance with validated data
            instance = Game.objects.update_by_id(kwargs['pk'], player, validated_data)[1]

            # Ensure the instance is valid and serialize it
            game_serializer = self.get_serializer(instance)
            if not game_serializer.is_valid():
                raise ValidationError("Game serializer data is not valid.")

            return Response(game_serializer.data)

        # If ChoiceSerializer data is not valid, raise a ValidationError
        raise ValidationError("ChoiceSerializer data is not valid")
