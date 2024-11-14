from django.contrib import admin
from .models import Match, TieBreaker

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'player_1', 'player_2', 'winner', 'match_state', 'match_type', 'start_date', 'end_date',
        'player_1_game_1_completed', 'player_1_game_2_completed', 'player_1_game_3_completed',
        'player_1_game_4_completed', 'player_1_game_5_completed',
        'player_2_game_1_completed', 'player_2_game_2_completed', 'player_2_game_3_completed',
        'player_2_game_4_completed', 'player_2_game_5_completed',
        'golden_game_completed'
    ]
    list_filter = ['match_state', 'match_type', 'start_date', 'end_date']
    search_fields = ['player_1__username', 'player_2__username', 'winner__username']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs

@admin.register(TieBreaker)
class TieBreakerAdmin(admin.ModelAdmin):
    list_display = ['id', 'winner', 'golden_game', 'total', 'owner_total', 'player_2_total']
    search_fields = ['winner__username', 'golden_game__id']
    readonly_fields = ['id', 'total', 'winner']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs
