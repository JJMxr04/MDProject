from rest_framework import serializers

from core.event.models import Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = "__all__"
        read_only_fields = ["created", "updated", "public_id"]

    def get_fields(self):
        # Mass-assignment guard: TeamSerializer is read-only in use (only read
        # via `.data` in tests; no write path). Force every field read-only so
        # `fields='__all__'` can't accept arbitrary input if it's ever wired to a
        # write endpoint. Reads are unaffected.
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields
