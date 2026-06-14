from django.contrib import admin

from core.ranking.models import Badge, PlayerProgress, Season, SeasonParticipation, XpEvent


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "start_date", "end_date"]
    list_filter = ["status"]
    prepopulated_fields = {"slug": ("name",)}
    # Model.clean() enforces no-overlap / one-ACTIVE / end>start — the admin
    # form surfaces ValidationError inline.


@admin.register(SeasonParticipation)
class SeasonParticipationAdmin(admin.ModelAdmin):
    list_display = ["user", "season", "season_points", "wins", "losses", "draws", "division", "final_rank"]
    list_filter = ["season", "division"]
    search_fields = ["user__email", "user__username"]
    autocomplete_fields = ["user"]


@admin.register(PlayerProgress)
class PlayerProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "level", "xp", "global_points", "lifetime_wins", "lifetime_losses", "all_time_rating"]
    search_fields = ["user__email", "user__username"]
    autocomplete_fields = ["user"]


@admin.register(XpEvent)
class XpEventAdmin(admin.ModelAdmin):
    list_display = ["user", "source", "amount", "match", "created_at"]
    list_filter = ["source"]
    search_fields = ["user__email", "user__username"]


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "type", "season", "earned_at"]
    list_filter = ["type", "season"]
    search_fields = ["user__email", "user__username"]
