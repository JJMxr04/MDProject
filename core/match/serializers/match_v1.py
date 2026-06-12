"""v1 read serializer for the match-detail island.

Explicit fields, all read-only. Players/winner are rendered through
``PublicUserSerializer`` (id/username/avatar only) so no privilege or contact
fields leak. Scores are computed properties.
"""

from rest_framework import serializers

from core.match.models import Match
from core.user.serializers import PublicUserSerializer


class MatchV1Serializer(serializers.ModelSerializer):
    player_1 = PublicUserSerializer(read_only=True)
    player_2 = PublicUserSerializer(read_only=True)
    winner = PublicUserSerializer(read_only=True)
    player_1_score = serializers.IntegerField(read_only=True)
    player_2_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "player_1",
            "player_2",
            "winner",
            "match_state",
            "match_type",
            "format",
            "start_date",
            "end_date",
            "player_1_score",
            "player_2_score",
        ]
        read_only_fields = fields
