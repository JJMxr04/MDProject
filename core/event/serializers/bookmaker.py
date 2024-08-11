from rest_framework import serializers
from core.event.models.bookmaker import Bookmaker
from core.event.serializers.event import EventSerializer
from core.event.serializers.market import MarketSerializer
from core.abstract.serializers import AbstractSerializer

class BookmakerSerializer(AbstractSerializer):
    event = EventSerializer()  # Nested serializer to include event details
    markets = MarketSerializer(many=True, read_only=True)  # Include markets associated with this bookmaker

    class Meta:
        model = Bookmaker
        fields = ['id', 'event', 'key', 'title', 'last_update', 'markets']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['markets'] = MarketSerializer(instance.markets.all(), many=True).data
        return rep
