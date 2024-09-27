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


class EventSerializer(AbstractSerializer):
    id = serializers.UUIDField(required=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    scores = TeamScoreSerializer(many=True, required=False, allow_null=True)
    home_team_team = serializers.SlugRelatedField(queryset=Team.objects.all(), slug_field='public_id')
    away_team_team = serializers.SlugRelatedField(queryset=Team.objects.all(), slug_field='public_id')
    # bookmakers = BookmakerSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        home_team_team = Team.objects.get_object_by_public_id(rep['home_team_team'])
        away_team_team = Team.objects.get_object_by_public_id(rep['away_team_team'])
        rep['home_team_team'] = TeamSerializer(home_team_team).data
        rep['away_team_team'] = TeamSerializer(away_team_team).data

        # The bookmakers field is not included in this serializer
        return rep

    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['created', 'updated']


class EventBookmakerSerializer(EventSerializer):
    # Remove the bookmakers field if it doesn't exist in the Event model
    # bookmakers = BookmakerSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Check if the instance has a method to get bookmakers or handle it differently
        # If there's no direct relation, you might need to fetch them differently
        # Example: rep['bookmakers'] = BookmakerSerializer(get_bookmakers_for_event(instance), many=True).data
        rep['bookmakers'] = []  # Set to an empty list or handle accordingly
        return rep
