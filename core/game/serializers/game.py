from rest_framework import serializers

from core.abstract.serializers import AbstractSerializer
from core.event.models import Event
from core.event.serializers.event import EventSerializer
from core.game.models import Game
from core.user.models import User
from core.user.serializers import PublicUserSerializer


class GameSerializer(AbstractSerializer):
    owner = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field="public_id")
    player_2 = serializers.SlugRelatedField(queryset=User.objects.all(), slug_field="public_id")
    event = serializers.SlugRelatedField(
        queryset=Event.objects.all(), slug_field="id", allow_null=True
    )

    is_golden = serializers.BooleanField(read_only=True)
    slot = serializers.IntegerField(read_only=True)

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        if rep.get("event") is not None:
            event = Event.objects.filter(id=rep["event"]).first()
            rep["event"] = EventSerializer(event).data if event else None

        owner = User.objects.get_object_by_public_id(rep["owner"])
        player_2 = User.objects.get_object_by_public_id(rep["player_2"])
        rep["owner"] = PublicUserSerializer(owner).data if owner else None
        rep["player_2"] = PublicUserSerializer(player_2).data if player_2 else None

        bet = instance.bet
        rep["bet"] = {
            "id": str(bet.id) if bet else None,
            "owner_outcome_id": bet.owner_outcome_id if bet else None,
            "player_2_outcome_id": bet.player_2_outcome_id if bet else None,
            "owner_decimal_odds_at_pick": (
                str(bet.owner_decimal_odds_at_pick)
                if bet and bet.owner_decimal_odds_at_pick is not None
                else None
            ),
            "player_2_decimal_odds_at_pick": (
                str(bet.player_2_decimal_odds_at_pick)
                if bet and bet.player_2_decimal_odds_at_pick is not None
                else None
            ),
        }
        return rep

    class Meta:
        model = Game
        fields = ["id", "owner", "player_2", "event", "is_golden", "slot", "match", "created", "updated"]
