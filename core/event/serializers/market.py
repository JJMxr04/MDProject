from core.abstract.serializers import AbstractSerializer
from core.event.models.market import Market
from .outcome import OutcomeSerializer
class MarketSerializer(AbstractSerializer):
    outcomes = OutcomeSerializer(many=True)

    class Meta:
        model = Market
        fields = ['key', 'last_update', 'outcomes']
