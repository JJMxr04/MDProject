from rest_framework import serializers
from core.event.models.bookmaker import Bookmaker
from core.event.serializers.market import MarketSerializer
from core.abstract.serializers import AbstractSerializer


class BookmakerSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    markets = MarketSerializer(many=True, read_only=True)

    class Meta:
        model = Bookmaker
        fields = ['key', 'title', 'last_update', 'markets']
        read_only_fields = ['created', 'updated']

    def to_representation(self, instance):
        # Call the super method to get the original serialized data
        rep = super().to_representation(instance)

        # You can directly return the original `markets` data from the `rep` dictionary
        return rep
