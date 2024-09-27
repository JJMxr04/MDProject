from rest_framework import serializers
from core.event.models.bookmaker import Bookmaker
from core.event.serializers.market import MarketSerializer
from core.abstract.serializers import AbstractSerializer
import json

class BookmakerSerializer(AbstractSerializer):
    markets = MarketSerializer(many=True, read_only=True)  # Include markets associated with this bookmaker

    class Meta:
        model = Bookmaker
        fields = ['id', 'key', 'title', 'last_update', 'markets']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Assuming 'event_id' is passed to filter markets by event
        event_id = self.context.get('event_id')  
        # Filter markets by both bookmaker and event
        rep['markets'] = MarketSerializer(instance.markets.filter(bookmaker=instance, event_id=event_id), many=True).data
        return rep
