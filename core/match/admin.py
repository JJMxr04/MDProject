# core/match/admin.py
from django.contrib import admin
from .models import Match

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'player_1', 'player_2', 'winner', 'match_state', 'match_type']
    list_filter = ['match_state', 'match_type']
    search_fields = ['player_1__username', 'player_2__username', 'winner__username']  # Assuming User model has username field

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Customize queryset as needed, e.g., filter by specific conditions
        return qs

    # Add more customization as needed

