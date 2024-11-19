from rest_framework import serializers

from core.event.models.event import Event
from core.event.models import Team, Bookmaker
from core.abstract.serializers import AbstractSerializer
from core.event.serializers.team import TeamSerializer
from .bookmaker import BookmakerSerializer




class TeamScoreSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_null=True)
    score = serializers.CharField(required=False, allow_null=True)

    class Meta:
        fields = '__all__'





class EventSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    scores = TeamScoreSerializer(many=True, required=False, allow_null=True)
    home_team_team = serializers.SlugRelatedField(queryset=Team.objects.all(), slug_field='public_id')
    away_team_team = serializers.SlugRelatedField(queryset=Team.objects.all(), slug_field='public_id')

    def validate(self, data):
        # Calculate the winner if the event is completed and scores are provided
        if data.get('completed') and data.get('scores'):
            scores = data['scores']
            if scores[0]['score'] > scores[1]['score']:
                data['winner'] = scores[0]['name']
            elif scores[0]['score'] < scores[1]['score']:
                data['winner'] = scores[1]['name']
            else:
                data['winner'] = 'Tie'
        return data

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        home_team = Team.objects.get_object_by_public_id(rep['home_team_team'])
        away_team = Team.objects.get_object_by_public_id(rep['away_team_team'])
        rep['home_team_team'] = TeamSerializer(home_team).data
        rep['away_team_team'] = TeamSerializer(away_team).data
        return rep


    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['created', 'updated']


class EventBookmakerSerializer(EventSerializer):
    bookmakers = BookmakerSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Always include the bookmakers in this serializer
        rep['bookmakers'] = BookmakerSerializer(instance.bookmakers.all(), many=True).data
        return rep
