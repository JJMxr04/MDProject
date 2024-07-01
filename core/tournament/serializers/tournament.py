from rest_framework import serializers
from core.tournament.models.tournament import Tournament, Round, InvitedPlayer,Player

from core.user.serializers import PublicUserSerializer
from core.tournament.serializers.tournament_components import InvitedPlayerSerializer, PlayerSerializer




class TournamentSerializer(serializers.ModelSerializer):
    invited_players = InvitedPlayerSerializer(many=True)
    players = PlayerSerializer(many=True)

    class Meta:
        model = Tournament
        fields = ['id', 'name', 'start_date', 'state', 'max_accepted_players', 'invited_players', 'players','final_round']

    def create(self, validated_data):
        invited_players_data = validated_data.pop('invited_players', [])
        players_data = validated_data.pop('players', [])

        tournament = Tournament.objects.create(**validated_data)

        for invited_player_data in invited_players_data:
            InvitedPlayer.objects.create(tournament=tournament, **invited_player_data)

        for player_data in players_data:
            Player.objects.create(tournament=tournament, **player_data)

        return tournament


class RoundSerializer(serializers.ModelSerializer):

    class Meta:
        model = Round
        fields = '__all__'
