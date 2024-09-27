from rest_framework import serializers
from core.event.models.market import Market
from core.event.serializers.outcome import OutcomeSerializer
from core.abstract.serializers import AbstractSerializer
from uuid import uuid4

class MarketSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=False, format='hex', allow_null=True)
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    outcomes = OutcomeSerializer(many=True, read_only=True)  # Include outcomes associated with this market

    class Meta:
        model = Market
        fields = '__all__'
        read_only_fields = ['created', 'updated']

    def create(self, validated_data):
        key = validated_data.pop('key')
        bookmaker_key = validated_data.pop('bookmaker_key')  # Assuming you pass bookmaker_key instead of the whole object
        bookmaker, created = Bookmaker.objects.get_or_create(key=bookmaker_key)
        
        market, created = Market.objects.get_or_create(key=key, bookmaker=bookmaker, defaults=validated_data)
        return market

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['outcomes'] = OutcomeSerializer(instance.outcomes.all(), many=True).data
        return rep
