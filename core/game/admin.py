# core/game/admin.py
from django.contrib import admin
from .models import Game, Bet

@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = ['id', 'market', 'owner_outcome', 'player_2_outcome', 'created_at', 'updated_at']
    list_filter = ['market']
    search_fields = ['market__name', 'owner_outcome__name', 'player_2_outcome__name']
    
    readonly_fields = ['id', 'created_at', 'updated_at']

    def owner_outcome_name(self, obj):
        return obj.owner_outcome.name if obj.owner_outcome else "-"
    
    def player_2_outcome_name(self, obj):
        return obj.player_2_outcome.name if obj.player_2_outcome else "-"

    owner_outcome_name.short_description = 'Owner Outcome'
    player_2_outcome_name.short_description = 'Player 2 Outcome'


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'owner', 'player_2',  'commence_time', 'deadline_time', 'completed', 'winner',
    ]
    list_filter = ['completed']
    search_fields = ['owner__username', 'player_2__username', 'match_id']

    readonly_fields = [
        'id', 'owner', 'player_2', 'match_id', 'commence_time', 'deadline_time',
        'completed', 'home_team', 'away_team', 'winner', 'owner_choice', 'player_2_choice', 'event'
    ]

    def event_link(self, obj):
        if obj.event:
            return f'<a href="/admin/event/event/{obj.event.id}/change/" target="_blank">{obj.event}</a>'
        return "-"
    event_link.short_description = 'Event'
    event_link.allow_tags = True

    def bet_link(self, obj):
        if hasattr(obj, 'bet'):
            return f'<a href="/admin/bet/bet/{obj.bet.id}/change/" target="_blank">View Bet</a>'
        return "-"
    bet_link.short_description = 'Bet'
    bet_link.allow_tags = True
