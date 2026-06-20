from rest_framework import serializers

from core.match.serializers.match import MatchSerializer
from core.tournament.models.tournament import InvitedPlayer, Player, Round, Tournament
from core.user.serializers import PublicUserSerializer


class PlayerSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = Player
        fields = ['id', 'tournament', 'player', 'seed', 'division']


class InviteSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = InvitedPlayer
        fields = ['id', 'tournament', 'player', 'accepted', 'accepted_date', 'invited_date', 'state']


class RoundSerializer(serializers.ModelSerializer):
    match = MatchSerializer()
    next_round = serializers.PrimaryKeyRelatedField(read_only=True)
    prev_round_1 = serializers.PrimaryKeyRelatedField(read_only=True)
    prev_round_2 = serializers.PrimaryKeyRelatedField(read_only=True)
    player_1 = PlayerSerializer()
    player_2 = PlayerSerializer()
    winner = PlayerSerializer()

    class Meta:
        model = Round
        fields = [
            'id', 'tournament', 'level_num', 'match', 'next_round',
            'prev_round_1', 'prev_round_2', 'player_1', 'player_2',
            'winner', 'completed'
        ]
        read_only_fields = [
            'id', 'tournament', 'level_num', 'match', 'next_round',
            'prev_round_1', 'prev_round_2', 'player_1', 'player_2',
            'winner', 'completed'
        ]


class TournamentSerializer(serializers.ModelSerializer):
    invited_players = InviteSerializer(many=True, read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    final_round = RoundSerializer()

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'start_date', 'state', 'max_accepted_players',
            'invited_players', 'players', 'final_round'
        ]

    def create(self, validated_data):
        # invited_players / players / final_round are read_only on this
        # serializer (see ``invited_players = InviteSerializer(..., read_only=True)``
        # above), so they're never present in validated_data. The previous
        # loops popped them anyway and called ``Invite.objects.create(...)``
        # with an undefined ``Invite`` symbol and a ``tournament`` kwarg
        # the model doesn't accept — pure dead-and-broken code. If those
        # fields ever become writable, use ``InvitedPlayer.objects.create_invited_player``
        # so the tournament-invite email fires.
        return Tournament.objects.create(**validated_data)
