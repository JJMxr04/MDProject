from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from core.abstract.serializers import AbstractSerializer
from core.game.serializers import GameSerializer
from core.match.models import Match, TieBreaker
from core.user.models import User
from core.user.serializers import PublicUserSerializer


class MatchSerializer(AbstractSerializer):
    player_1 = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field="public_id"
    )
    player_2 = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field="public_id", allow_null=True
    )
    winner = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field="public_id", allow_null=True
    )
    tiebreaker = serializers.SlugRelatedField(
        queryset=TieBreaker.objects.all(), slug_field="id", allow_null=True
    )

    player_1_score = serializers.IntegerField(read_only=True)
    player_2_score = serializers.IntegerField(read_only=True)

    player_1_games = serializers.SerializerMethodField()
    player_2_games = serializers.SerializerMethodField()
    golden_game = serializers.SerializerMethodField()

    def validate_players(self):
        if (
            self.context["request"].user != self.player_1
            and self.context["request"] != self.player_2
        ):
            raise ValidationError("You cannot update this match")

    def get_player_1_games(self, obj):
        return GameSerializer(obj.regular_games_for(obj.player_1), many=True).data

    def get_player_2_games(self, obj):
        if obj.player_2 is None:
            return []
        return GameSerializer(obj.regular_games_for(obj.player_2), many=True).data

    def get_golden_game(self, obj):
        gg = obj.golden_game
        return GameSerializer(gg).data if gg else None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        player_1 = User.objects.get_object_by_public_id(rep["player_1"])
        rep["player_1"] = PublicUserSerializer(player_1).data

        if rep["player_2"] is not None:
            player_2 = User.objects.get_object_by_public_id(rep["player_2"])
            rep["player_2"] = PublicUserSerializer(player_2).data

        if rep["winner"] is not None:
            winner = User.objects.get_object_by_public_id(rep["winner"])
            rep["winner"] = PublicUserSerializer(winner).data

        if rep["tiebreaker"] is not None:
            tiebreaker = TieBreaker.objects.get(pk=rep["tiebreaker"])
            rep["tiebreaker"] = {
                "id": str(tiebreaker.id),
                "winner": PublicUserSerializer(tiebreaker.winner).data if tiebreaker.winner else None,
            }

        return rep

    class Meta:
        model = Match
        fields = [
            "id",
            "player_1",
            "player_2",
            "winner",
            "match_state",
            "match_type",
            "tiebreaker",
            "start_date",
            "end_date",
            "player_1_score",
            "player_2_score",
            "player_1_games",
            "player_2_games",
            "golden_game",
            "created",
            "updated",
        ]
