from rest_framework import serializers

from core.event.models import Team

from core.abstract.serializers import AbstractSerializer


class TeamSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)


    class Meta:
        model = Team
        fields = '__all__'  # Include all fields
        # List of all the fields that can only be read by the user
        read_only_fields = ['created', 'updated']