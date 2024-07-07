from rest_framework import serializers
from core.tournament.models.tournament import Tournament, Round, InvitedPlayer, Player
from core.user.serializers import PublicUserSerializer


class PlayerSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = Player
        fields = ['id', 'tournament', 'player', 'seed', 'division']


class InvitedPlayerSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = InvitedPlayer
        fields = ['id', 'tournament', 'player', 'accepted', 'accepted_date', 'invited_date', 'state']


class RoundSerializer(serializers.ModelSerializer):
    match = serializers.StringRelatedField()
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
        read_only = [
            'id', 'tournament', 'level_num', 'match', 'next_round',
            'prev_round_1', 'prev_round_2', 'player_1', 'player_2',
            'winner', 'completed'
        ]


class TournamentSerializer(serializers.ModelSerializer):
    invited_players = InvitedPlayerSerializer(many=True, read_only=True)
    players = PlayerSerializer(many=True, read_only=True)
    final_round = RoundSerializer()

    class Meta:
        model = Tournament
        fields = [
            'id', 'name', 'start_date', 'state', 'max_accepted_players',
            'invited_players', 'players', 'final_round'
        ]

    def create(self, validated_data):
        invited_players_data = validated_data.pop('invited_players', [])
        players_data = validated_data.pop('players', [])
        final_round_data = validated_data.pop('final_round', None)

        tournament = Tournament.objects.create(**validated_data)

        for invited_player_data in invited_players_data:
            InvitedPlayer.objects.create(tournament=tournament, **invited_player_data)

        for player_data in players_data:
            Player.objects.create(tournament=tournament, **player_data)

        if final_round_data:
            Round.objects.create(tournament=tournament, **final_round_data)

        return tournament
