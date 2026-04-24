from rest_framework import serializers

from core.event.models import Selection
from core.event.odds.converters import (
    decimal_to_american,
    decimal_to_fractional,
    movement_label,
)


class OddsFormatsField(serializers.Field):
    """Serializes a `Selection` to the three-format odds object."""

    def to_representation(self, selection: Selection):
        d = selection.decimal_odds
        return {
            "decimal": float(d),
            "american": decimal_to_american(d),
            "fractional": decimal_to_fractional(d),
        }


class SelectionSerializer(serializers.ModelSerializer):
    selection_id = serializers.IntegerField(source="id", read_only=True)
    odds = serializers.SerializerMethodField()
    movement = serializers.SerializerMethodField()
    is_winner = serializers.SerializerMethodField()

    class Meta:
        model = Selection
        fields = [
            "selection_id",
            "type",
            "label",
            "odds",
            "movement",
            "suspended",
            "is_winner",
            "settlement_status",
            "settled_at",
        ]

    def get_odds(self, obj):
        return OddsFormatsField().to_representation(obj)

    def get_movement(self, obj):
        return movement_label(obj.movement)

    def get_is_winner(self, obj):
        if obj.settlement_status == "WON":
            return True
        if obj.settlement_status == "LOST":
            return False
        return None  # PENDING, PUSH, VOID
