from rest_framework import serializers

from core.event.models.event import Event

from core.abstract.serializers import AbstractSerializer

class TeamScoreSerializer(serializers.Serializer):
    name = serializers.CharField()
    score = serializers.CharField()
class EventSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    scores = TeamScoreSerializer(many=True, required=False,allow_null=True)

    class Meta:
        model = Event
        fields = '__all__'  # Include all fields
        # List of all the fields that can only be read by the user
        read_only_fields = ['id', 'created', 'updated']

