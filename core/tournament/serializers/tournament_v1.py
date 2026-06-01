from rest_framework import serializers

from core.tournament.models.tournament import Player, Round, Tournament
from core.user.serializers import PublicUserSerializer


class PlayerV1Serializer(serializers.ModelSerializer):
    player = PublicUserSerializer(read_only=True)

    class Meta:
        model = Player
        fields = ["id", "player", "seed", "division"]
        read_only_fields = fields


class TournamentV1Serializer(serializers.ModelSerializer):
    players = PlayerV1Serializer(many=True, read_only=True)

    class Meta:
        model = Tournament
        fields = [
            "id",
            "name",
            "description",
            "start_date",
            "end_date",
            "state",
            "max_accepted_players",
            "levels",
            "players",
        ]
        read_only_fields = fields


class RoundV1Serializer(serializers.ModelSerializer):
    player_1 = PlayerV1Serializer(read_only=True)
    player_2 = PlayerV1Serializer(read_only=True)
    winner = PlayerV1Serializer(read_only=True)

    class Meta:
        model = Round
        fields = [
            "id",
            "tournament",
            "level_num",
            "player_1",
            "player_2",
            "winner",
            "completed",
        ]
        read_only_fields = fields
