from core.abstract.serializers import AbstractSerializer
from core.event.models.outcome import Outcome

class OutcomeSerializer(AbstractSerializer):
    class Meta:
        model = Outcome
        fields = ['name', 'price', 'point']
