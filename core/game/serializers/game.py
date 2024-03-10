from rest_framework import serializers
from core.game.models import Game
from core.abstract.serializers import AbstractSerializer
from core.user.models import User
from core.user.serializers import UserSerializer, PublicUserSerializer
from core.event.serializers.event import EventSerializer

from core.event.models import Event


class GameSerializer(AbstractSerializer):
    owner = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')
    event = serializers.SlugRelatedField(queryset=Event.objects.all(), slug_field='id')

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        owner = User.objects.get_object_by_public_id(rep['owner'])
        player_2 = User.objects.get_object_by_public_id(rep['player_2'])
        # event = Event.objects.get_object_by_id(rep['event'])

        # Check if 'event' is None, and set it to None if it is
        if rep['event'] is None:
            rep['event'] = None
        else:
            event = Event.objects.get_object_by_id(rep['event'])
            rep['event'] = EventSerializer(event).data

        # Convert owner and player_2 to PublicUserSerializer representation
        rep['owner'] = PublicUserSerializer(owner).data
        rep['player_2'] = PublicUserSerializer(player_2).data

        return rep

    class Meta:
        model = Game
        fields = '__all__'