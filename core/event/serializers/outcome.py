from uuid import uuid4
from rest_framework import serializers
from core.event.models.outcome import Outcome
from core.abstract.serializers import AbstractSerializer

class OutcomeSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=False, format='hex', allow_null=True)
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Outcome
        fields = '__all__'
        read_only_fields = ['created', 'updated']

    def create(self, validated_data):
        # Generate a UUID if 'id' is not provided
        if 'id' not in validated_data:
            validated_data['id'] = uuid4()

        return super().create(validated_data)

    def validate_name(self, value):
        # Ensure the name field has no more than 50 characters
        if len(value) > 50:
            raise serializers.ValidationError("Ensure this field has no more than 50 characters.")
        return value
