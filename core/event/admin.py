from django.contrib import admin
from .models import Event
import json

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'sport_title', 'group', 'commence_time', 'completed', 'winner', 'formatted_scores']
    list_filter = ['sport_title', 'group', 'completed']
    search_fields = ['title', 'description', 'sport_title', 'group', 'winner']

    fieldsets = (
        (None, {
            'fields': ('sport_key', 'sport_title', 'title', 'group', 'description', 'commence_time', 'completed', 'winner')
        }),
        ('Teams', {
            'fields': ('home_team', 'home_team_team', 'away_team', 'away_team_team')
        }),
        ('Scores', {
            'fields': ('scores',)
        }),
    )

    readonly_fields = ('sport_key', 'sport_title', 'title', 'group', 'description', 'commence_time', 'completed', 'winner', 'home_team', 'home_team_team', 'away_team', 'away_team_team', 'formatted_scores', 'scores')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.completed:
            readonly_fields += ('scores',)
        return readonly_fields

    def formatted_scores(self, obj):
        return "WIP"
        # try:
        #     scores = obj.scores
        #     if scores:
        #         scores_data = json.loads(scores)
        #         if isinstance(scores_data, list):
        #             team_scores = []
        #             for score in scores_data:
        #                 if isinstance(score, dict) and 'name' in score and 'score' in score:
        #                     team_scores.append(f"{score['name']}: {score['score']}")
        #                 else:
        #                     return f"Invalid score format: {score}"
        #             return ", ".join(team_scores)
        #         else:
        #             return "Invalid scores data"
        #     else:
        #         return "No scores available"
        # except json.JSONDecodeError as e:
        #     return f"Error parsing scores: {e}"
        # except Exception as e:
        #     return f"Unexpected error: {e}"

    formatted_scores.short_description = 'Scores'