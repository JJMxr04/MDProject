from django.contrib import admin
from .models import Event, Sport, Team, Bookmaker, Market, Outcome

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'sport_title', 'group', 'commence_time', 'completed', 'winner', 'formatted_scores', 'home_team_team', 'away_team_team']
    list_filter = ['sport_title', 'group', 'completed']
    search_fields = ['title', 'description', 'sport_title', 'group', 'winner', 'commence_time', 'completed', 'home_team_team__team_name', 'away_team_team__team_name']

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

    readonly_fields = ('sport_key', 'sport_title', 'title', 'group', 'description', 'commence_time', 'home_team', 'home_team_team', 'away_team', 'away_team_team')

    # def get_readonly_fields(self, request, obj=None):
    #     readonly_fields = super().get_readonly_fields(request, obj)
    #     if obj and obj.completed:
    #         readonly_fields += ('scores',)
    #     return readonly_fields

    def formatted_scores(self, obj):
        return "WIP"
        # Add your logic for formatted scores here
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

@admin.register(Bookmaker)
class BookmakerAdmin(admin.ModelAdmin):
    list_display = ['id', 'key', 'title', 'event', 'last_update']
    search_fields = ['id', 'key', 'title', 'event__title', 'event__id']  # Added event__id for searching by event_id
    readonly_fields = ['id', 'last_update']

    fieldsets = (
        (None, {
            'fields': ('id', 'event', 'last_update')  # Added missing comma here
        }),
    )

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ['key', 'bookmaker', 'last_update']
    search_fields = ['key', 'bookmaker__title']  # Assuming 'name' field was a typo and should be 'title'
    readonly_fields = ['id','last_update']

    fieldsets = (
        (None, {
            'fields': ('key', 'bookmaker', 'last_update')
        }),
    )

@admin.register(Outcome)
class OutcomeAdmin(admin.ModelAdmin):
    list_display = ['name', 'market', 'price','point']
    search_fields = ['name', 'market__key']
    readonly_fields = ['price']

    fieldsets = (
        (None, {
            'fields': ('name', 'market', 'price','point')
        }),
    )
