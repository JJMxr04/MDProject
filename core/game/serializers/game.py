from rest_framework import serializers
from core.game.models import Game
from core.abstract.serializers import AbstractSerializer
from core.user.models import User
from core.user.serializers import UserSerializer, PublicUserSerializer

class GameSerializer(AbstractSerializer):

    owner = serializers.SlugRelatedField(queryset=User.objects.all(),slug_field='public_id')
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        owner = User.objects.get_object_by_public_id(rep['owner'])
        player_2 = User.objects.get_object_by_public_id(rep['player_2'])
        rep['owner'] = PublicUserSerializer(owner).data
        rep['player_2'] = PublicUserSerializer(player_2).data
        return rep
    class Meta:
        model = Game
        fields = '__all__'
