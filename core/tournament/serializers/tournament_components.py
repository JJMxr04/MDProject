from rest_framework import serializers
from core.tournament.models.tournament import Tournament, Invite, Player
from core.user.serializers import PublicUserSerializer

class InviteSerializer(serializers.ModelSerializer):
    player = PublicUserSerializer()

    class Meta:
        model = Invite
        fields = ['player', 'accepted', 'accepted_date', 'invited_date']

    def create(self, validated_data):
        tournament = self.context['tournament']
        player_data = validated_data.pop('player')
        invited_player = Invite.objects.create(tournament=tournament, **validated_data)
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