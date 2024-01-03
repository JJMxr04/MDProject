from rest_framework import serializers
from core.match.models import Match
from core.abstract.serializers import AbstractSerializer

class MatchSerializer(AbstractSerializer):
    class Meta:
        model = Match
        fields = '__all__'
