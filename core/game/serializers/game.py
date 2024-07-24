from rest_framework import serializers
from core.game.models import Game
from core.event.models import Team
from core.event.models import Event
from core.abstract.serializers import AbstractSerializer
from core.user.models import User
from core.user.serializers import UserSerializer, PublicUserSerializer
from core.event.serializers.team import TeamSerializer
from core.event.serializers.event import EventSerializer
from rest_framework.exceptions import ValidationError
from rest_framework import serializers
  # Import your models here

class ChoiceSerializer(serializers.Serializer):
    event = serializers.SlugRelatedField(queryset=Event.objects.all(), slug_field='id')
    player_choice = serializers.SlugRelatedField(queryset=Team.objects.all(), slug_field='public_id')

    # Add any additional validation methods if needed
    def validate_event(self, value):
        # Add custom validation for event if necessary
        return value

    def validate_player_choice(self, value):
        # Add custom validation for player_choice if necessary
        return value
class GameSerializer(AbstractSerializer):
    owner = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field='public_id')
    event = serializers.SlugRelatedField(queryset=Event.objects.all(), slug_field='id')

    def validate_players(self):
        if (self.context["request"].user != self.owner) and (self.context["request"] != self.player_2):
            raise ValidationError("You cannot Update This Game")

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