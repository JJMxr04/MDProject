from django.contrib import admin
from .models import Sport
from .models import Event
from .models import Team

@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ['key', 'title', 'group', 'active', 'has_outrights']
    list_filter = ['active', 'has_outrights']
    search_fields = ['key', 'title', 'group']

    fieldsets = (
        (None, {
            'fields': ('key', 'title', 'group', 'description', 'active', 'has_outrights')
        }),
    )

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['title', 'sport_title', 'group', 'commence_time', 'completed', 'winner']
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

    readonly_fields = ('winner',)  # Ensure 'winner' field is read-only in admin

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj and obj.completed:
            readonly_fields += ('completed', 'scores', 'home_team', 'home_team_team', 'away_team', 'away_team_team')
        return readonly_fields

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'title', 'group', 'team_id', 'logo_url', 'country', 'country_code']
    search_fields = ['team_name', 'title', 'group', 'country']

    fieldsets = (
        (None, {
            'fields': ('team_name', 'title', 'group')
        }),
        ('Team Details', {
            'fields': ('team_id', 'logo_url', 'country', 'country_code')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make 'public_id' field read-only
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj:
            readonly_fields += ('public_id',)
        return readonly_fields