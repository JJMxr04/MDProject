# core/game/admin.py
from django.contrib import admin
from .models import Game

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'owner', 'player_2', 'match_id', 'commence_time', 'deadline_time', 'completed',
        'home_team', 'away_team', 'winner', 'owner_choice', 'player_2_choice', 'event_link'
    ]
    list_filter = ['completed']
    search_fields = ['owner__username', 'player_2__username', 'match_id']

    readonly_fields = [
        'id', 'owner', 'player_2', 'match_id', 'commence_time', 'deadline_time',
        'completed', 'home_team', 'away_team', 'winner', 'owner_choice', 'player_2_choice', 'event'
    ]

    def event_link(self, obj):
        if obj.event:
            link = f'<a href="/admin/event/event/{obj.event.id}/change/" target="_blank">{obj.event}</a>'
            return link
        return "-"
    event_link.short_description = 'Event'
    event_link.allow_tags = True
