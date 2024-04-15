from rest_framework import serializers
from core.tournament.models.tournament import Tournament, InvitedPlayer, Player
from core.user.serializers import PublicUserSerializer


class InvitedPlayerSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = InvitedPlayer
        fields = ['player', 'accepted', 'accepted_date', 'invited_date']

    def create(self, validated_data):
        tournament = self.context['tournament']
        player_data = validated_data.pop('player')
        invited_player = InvitedPlayer.objects.create(tournament=tournament, **validated_data)
        invited_player.player.set(player_data)
        return invited_player


class PlayerSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = Player
        fields = ['player', 'seed']

    def create(self, validated_data):
        tournament = self.context['tournament']
        player_data = validated_data.pop('player')
        player = Player.objects.create(tournament=tournament, **validated_data)
        player.player.set(player_data)
        return player


class TournamentSerializer(serializers.ModelSerializer):
    invited_players = InvitedPlayerSerializer(many=True)
    players = PlayerSerializer(many=True)

    class Meta:
        model = Tournament
        fields = ['id', 'name', 'start_date', 'end_date', 'state', 'max_accepted_players', 'invited_players', 'players']

    def create(self, validated_data):
        invited_players_data = validated_data.pop('invited_players', [])
        players_data = validated_data.pop('players', [])

        tournament = Tournament.objects.create(**validated_data)

        for invited_player_data in invited_players_data:
            InvitedPlayer.objects.create(tournament=tournament, **invited_player_data)

        for player_data in players_data:
            Player.objects.create(tournament=tournament, **player_data)

        return tournament
