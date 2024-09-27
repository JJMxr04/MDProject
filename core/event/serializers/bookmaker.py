from rest_framework import serializers
from core.event.models.bookmaker import Bookmaker
from core.event.serializers.market import MarketSerializer
from core.abstract.serializers import AbstractSerializer

class BookmakerSerializer(AbstractSerializer):
    markets = MarketSerializer(many=True, read_only=True)  # Include markets associated with this bookmaker

    class Meta:
        model = Bookmaker
        fields = ['id', 'event', 'key', 'title', 'last_update', 'markets']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['markets'] = MarketSerializer(instance.markets.all(), many=True).data
        return rep

    def create(self, validated_data):
        key = validated_data.get('key')
        bookmaker, created = Bookmaker.objects.get_or_create(key=key, defaults=validated_data)
        return bookmaker
