from rest_framework import serializers
from core.match.models import Match
from core.abstract.serializers import AbstractSerializer
from core.user.models import  User
from core.user.serializers import UserSerializer, PublicUserSerializer
from core.game.models import Game
from core.game.serializers import GameSerializer

class MatchSerializer(AbstractSerializer):

    player_1 = serializers.SlugRelatedField(queryset=User.objects.all(),slug_field='public_id')
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        player_1 = User.objects.get_object_by_public_id(rep['player_1'])
        player_2 = User.objects.get_object_by_public_id(rep['player_2'])
        player_1_game_1 = Game.objects.get_object_by_id(rep['player_1_game_1'])
        player_1_game_2 = Game.objects.get_object_by_id(rep['player_1_game_2'])
        player_1_game_3 = Game.objects.get_object_by_id(rep['player_1_game_3'])
        player_1_game_4 = Game.objects.get_object_by_id(rep['player_1_game_4'])
        player_1_game_5 = Game.objects.get_object_by_id(rep['player_1_game_5'])
        player_2_game_1 = Game.objects.get_object_by_id(rep['player_2_game_1'])
        player_2_game_2 = Game.objects.get_object_by_id(rep['player_2_game_2'])
        player_2_game_3 = Game.objects.get_object_by_id(rep['player_2_game_3'])
        player_2_game_4 = Game.objects.get_object_by_id(rep['player_2_game_4'])
        player_2_game_5 = Game.objects.get_object_by_id(rep['player_2_game_5'])
        golden_game = Game.objects.get_object_by_id(rep['golden_game'])
        rep['player_1'] = PublicUserSerializer(player_1).data
        rep['player_2'] = PublicUserSerializer(player_2).data
        rep['player_1_game_1'] = GameSerializer(player_1_game_1).data
        rep['player_1_game_2'] = GameSerializer(player_1_game_2).data
        rep['player_1_game_3'] = GameSerializer(player_1_game_3).data
        rep['player_1_game_4'] = GameSerializer(player_1_game_4).data
        rep['player_1_game_5'] = GameSerializer(player_1_game_5).data
        rep['player_2_game_1'] = GameSerializer(player_2_game_1).data
        rep['player_2_game_2'] = GameSerializer(player_2_game_2).data
        rep['player_2_game_3'] = GameSerializer(player_2_game_3).data
        rep['player_2_game_4'] = GameSerializer(player_2_game_4).data
        rep['player_2_game_5'] = GameSerializer(player_2_game_5).data
        rep['golden_game'] = GameSerializer(golden_game).data
        return rep
    class Meta:
        model = Match
        fields = '__all__'
