from rest_framework import serializers

from core.event.models import Event

from .market import MarketSerializer


# SGO sportID -> public slug used by the Flutter client.
SPORT_SLUG_MAP = {
    "BASEBALL": "baseball",
    "BASKETBALL": "basketball",
    "FOOTBALL": "american_football",
    "HOCKEY": "ice_hockey",
    "SOCCER": "soccer",
}


class _TeamBriefField(serializers.Field):
    def to_representation(self, team):
        if team is None:
            return None
        return {
            "id": team.id,
            "team_id": team.team_id,
            "name": team.name_long,
            "short": team.name_short or team.name_medium or team.name_long,
            "logo_url": team.logo_url,
        }


class EventSerializer(serializers.ModelSerializer):
    event_id = serializers.CharField(source="id", read_only=True)
    sport = serializers.SerializerMethodField()
    league = serializers.SerializerMethodField()
    home_team = serializers.SerializerMethodField()
    away_team = serializers.SerializerMethodField()
    is_live = serializers.SerializerMethodField()
    status = serializers.CharField(source="status_type", read_only=True)

    class Meta:
        model = Event
        fields = [
            "event_id",
            "sport",
            "league",
            "home_team",
            "away_team",
            "start_time",
            "status",
            "is_live",
            "home_score",
            "away_score",
            "winner_code",
        ]

    def get_sport(self, obj):
        return SPORT_SLUG_MAP.get(obj.sport_id, (obj.sport_id or "").lower() or None)

    def get_league(self, obj):
        if obj.league_id is None:
            return None
        return {
            "id": obj.league_id,
            "name": obj.league.name if obj.league else obj.league_id,
            "short_name": obj.league.short_name if obj.league else "",
        }

    def get_home_team(self, obj):
        return _TeamBriefField().to_representation(obj.home_team)

    def get_away_team(self, obj):
        return _TeamBriefField().to_representation(obj.away_team)

    def get_is_live(self, obj):
        return obj.status_type == "inprogress"


class EventWithMarketsSerializer(EventSerializer):
    markets = serializers.SerializerMethodField()

    class Meta(EventSerializer.Meta):
        fields = EventSerializer.Meta.fields + ["markets"]

    def get_markets(self, obj):
        qs = obj.markets.prefetch_related("selections").all()

        # Optional trimming: caller can pass request.context["top_only"]=True
        # to inline only one marquee market per category (for list screens).
        if self.context.get("top_only"):
            wanted = {"MONEYLINE": None, "SPREAD": None, "TOTAL": None}
            for m in qs.filter(scope="FULL_GAME").order_by("category", "line"):
                if m.category in wanted and wanted[m.category] is None:
                    wanted[m.category] = m
            qs = [m for m in wanted.values() if m is not None]

        return MarketSerializer(qs, many=True, context=self.context).data
