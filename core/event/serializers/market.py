from rest_framework import serializers
from core.event.models.market import Market
from core.event.serializers.outcome import OutcomeSerializer
from core.abstract.serializers import AbstractSerializer

class MarketSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    outcomes = OutcomeSerializer(many=True, read_only=True)

    class Meta:
        model = Market
        fields = '__all__'
        read_only_fields = ['created', 'updated']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['outcomes'] = OutcomeSerializer(instance.outcomes.all(), many=True).data
        return rep
