from rest_framework import serializers
from core.event.models.outcome import Outcome
from core.abstract.serializers import AbstractSerializer

class OutcomeSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Outcome
        fields = '__all__'
        read_only_fields = ['created', 'updated']
