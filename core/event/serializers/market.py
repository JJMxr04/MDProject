from rest_framework import serializers

from core.event.models import Market

from .selection import SelectionSerializer


class MarketSerializer(serializers.ModelSerializer):
    market_id = serializers.CharField(source="id", read_only=True)
    selections = SelectionSerializer(many=True, read_only=True)
    line = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()

    class Meta:
        model = Market
        fields = [
            "market_id",
            "category",
            "type",
            "scope",
            "line",
            "side",
            "subject",
            "suspended",
            "is_live",
            "last_updated",
            "selections",
        ]

    def get_line(self, obj):
        return float(obj.line) if obj.line is not None else None

    def get_subject(self, obj):
        if obj.subject_team_id:
            team = obj.subject_team
            return {"kind": "team", "id": team.id, "name": team.name}
        return None
