from rest_framework import serializers

from core.event.models import Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"
        read_only_fields = ["created", "updated", "public_id"]
