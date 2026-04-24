from django.contrib import admin

from .models import Match, TieBreaker


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "player_1",
        "player_2",
        "winner",
        "match_state",
        "match_type",
        "start_date",
        "end_date",
    ]
    list_filter = ["match_state", "match_type", "start_date", "end_date"]
    search_fields = ["player_1__username", "player_2__username", "winner__username"]


@admin.register(TieBreaker)
class TieBreakerAdmin(admin.ModelAdmin):
    list_display = ["id", "winner", "golden_game", "total", "owner_total", "player_2_total"]
    search_fields = ["winner__username", "golden_game__id"]
    readonly_fields = ["id", "total", "winner"]
