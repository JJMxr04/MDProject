from django.contrib import admin
from .models import Match

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
    readonly_fields = [
        'id', 'winner', 'match_state', 'match_type',
        'player_1_score', 'player_2_score',
        'player_1_game_1', 'player_1_game_1_completed',
        'player_1_game_2', 'player_1_game_2_completed',
        'player_1_game_3', 'player_1_game_3_completed',
        'player_1_game_4', 'player_1_game_4_completed',
        'player_1_game_5', 'player_1_game_5_completed',
        'player_2_game_1', 'player_2_game_1_completed',
        'player_2_game_2', 'player_2_game_2_completed',
        'player_2_game_3', 'player_2_game_3_completed',
        'player_2_game_4', 'player_2_game_4_completed',
        'player_2_game_5', 'player_2_game_5_completed',
        'golden_game', 'golden_game_completed'
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Customize queryset as needed, e.g., filter by specific conditions
        return qs
