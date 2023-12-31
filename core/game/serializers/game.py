from rest_framework import serializers
from core.game.models import Game
from core.abstract.serializers import AbstractSerializer

class GameSerializer(AbstractSerializer):
    class Meta:
        model = Game
        fields = '__all__'
