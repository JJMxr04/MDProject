from django.contrib import admin
from .models import Event
from .models import Sport
from .models import Team
import json

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'sport_title', 'group', 'commence_time', 'completed', 'winner', 'formatted_scores','home_team_team','away_team_team']
    list_filter = ['sport_title', 'group', 'completed']
    search_fields = ['title', 'description', 'sport_title', 'group', 'winner','commence_time', 'completed', 'winner', 'home_team_team__team_name','away_team_team__team_name']

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


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'title', 'group', 'team_id', 'logo_url', 'country', 'country_code']
    search_fields = ['team_name', 'title', 'team_id', 'country']
    readonly_fields = ['public_id']

    fieldsets = (
        (None, {
            'fields': ('team_name', 'title', 'group', 'team_id', 'logo_url', 'country', 'country_code')
        }),
        ('Identifiers', {
            'fields': ('public_id',),
            'classes': ('collapse',),
        }),
    )


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'group', 'active', 'has_outrights', 'created', 'updated']
    list_filter = ['active', 'has_outrights']
    search_fields = ['key', 'title', 'group', 'description']
    readonly_fields = ['created', 'updated']

    fieldsets = (
        (None, {
            'fields': ('key', 'title', 'group', 'description', 'active', 'has_outrights')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',),
        }),
    )