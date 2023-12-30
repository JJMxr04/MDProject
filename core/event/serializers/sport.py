from rest_framework import serializers

from core.event.models.sport import Sport

from core.abstract.serializers import AbstractSerializer


class SportSerializer(AbstractSerializer):
    class Meta:
        model = Sport
        fields = '__all__'
        # read_only_fields = '__all__'
class TeamScoreSerializer(serializers.Serializer):
    name = serializers.CharField()
    score = serializers.CharField()
