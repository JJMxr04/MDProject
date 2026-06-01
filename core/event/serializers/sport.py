from rest_framework import serializers

from core.event.models.sport import Sport


class SportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sport
        fields = '__all__'

    def get_fields(self):
        # S-17 (mass-assignment): this serializer is read-only in use (catalog /
        # reference data; SportViewSet is GET-only). Force every field read-only
        # so `fields='__all__'` can never become a write/mass-assignment vector
        # if it's ever attached to a write path. Reads are unaffected —
        # read-only fields are still serialized for output.
        fields = super().get_fields()
        for field in fields.values():
            field.read_only = True
        return fields
