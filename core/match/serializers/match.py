from rest_framework import serializers
from core.match.models import Match
from core.abstract.serializers import AbstractSerializer
from core.user.models import  User
from core.user.serializers import UserSerializer, PublicUserSerializer
from core.game.models import Game
from core.game.serializers import GameSerializer
from rest_framework.exceptions import ValidationError

class MatchSerializer(AbstractSerializer):

    player_1 = serializers.SlugRelatedField(queryset=User.objects.all(),slug_field='public_id')
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(),slug_field='public_id',allow_null=True)

    def validate_players(self):
        if (self.context["request"].user != self.player_1) and (self.context["request"] != self.player_2):
            raise ValidationError("You cannot Update This Game")

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        player_1 = User.objects.get_object_by_public_id(rep['player_1'])

        # Process player_1_game_x fields
        for i in range(1, 6):
            player_1_game_key = f'player_1_game_{i}'
            if rep[player_1_game_key] is not None:
                rep[player_1_game_key] = GameSerializer(Game.objects.get_object_by_id(rep[player_1_game_key])).data

        if rep['player_2'] is not None:
            player_2 = User.objects.get_object_by_public_id(rep['player_2'])
            rep['player_2'] = PublicUserSerializer(player_2).data

            # Process player_2_game_x fields
            for i in range(1, 6):
                player_2_game_key = f'player_2_game_{i}'
                if rep[player_2_game_key] is not None:
                    rep[player_2_game_key] = GameSerializer(Game.objects.get_object_by_id(rep[player_2_game_key])).data

        # Process golden_game field
        if rep['golden_game'] is not None:
            rep['golden_game'] = GameSerializer(Game.objects.get_object_by_id(rep['golden_game'])).data

        rep['player_1'] = PublicUserSerializer(player_1).data

        return rep
    class Meta:
        model = Match
        fields = '__all__'
