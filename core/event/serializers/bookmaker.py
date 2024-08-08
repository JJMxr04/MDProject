
from core.abstract.serializers import AbstractSerializer
from core.event.models.bookmaker import Bookmaker
from .market import MarketSerializer


class BookmakerSerializer(AbstractSerializer):
    markets = MarketSerializer(many=True)

    class Meta:
        model = Bookmaker
        fields = ['key', 'title', 'last_update', 'markets']