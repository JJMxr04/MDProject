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
    bookmakers = BookmakerSerializer(many=True, required=False)

    def __init__(self, *args, **kwargs):
        # Retrieve the 'include_bookmakers' flag, defaulting to True if not provided
        self.include_bookmakers = kwargs.pop('include_bookmakers', True)
        super().__init__(*args, **kwargs)

    def get_bookmakers(self, obj):
        # Return bookmakers only if the flag is set
        if self.include_bookmakers:
            return BookmakerSerializer(obj.bookmakers.all(), many=True).data
        return None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        home_team_team = Team.objects.get_object_by_public_id(rep['home_team_team'])
        away_team_team = Team.objects.get_object_by_public_id(rep['away_team_team'])
        rep['home_team_team'] = TeamSerializer(home_team_team).data
        rep['away_team_team'] = TeamSerializer(away_team_team).data

        return rep

    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['created', 'updated']

    class Meta:
        model = Event
        fields = '__all__'
        read_only_fields = ['created', 'updated']

