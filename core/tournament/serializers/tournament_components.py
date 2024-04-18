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