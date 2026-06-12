from django.contrib import admin

from core.potd.models import DailyPick, PickOfDay


@admin.register(PickOfDay)
class PickOfDayAdmin(admin.ModelAdmin):
    """Manual-curation override: create/replace a day's pick here and the
    nightly cron will leave it alone (it never overwrites an existing row).
    Use raw event/market ids; lock_time should match the event kickoff."""
    list_display = ["date", "event", "market", "lock_time", "manually_curated", "pick_count"]
    list_filter = ["manually_curated"]
    search_fields = ["event__id", "event__home_team__name_long", "event__away_team__name_long"]
    raw_id_fields = ["event", "market"]
    readonly_fields = ["created_at"]
    ordering = ["-date"]

    def pick_count(self, obj):
        return obj.picks.count()

    def save_model(self, request, obj, form, change):
        # Anything touched by a human in the admin counts as curated.
        obj.manually_curated = True
        if not obj.lock_time and obj.event and obj.event.start_time:
            obj.lock_time = obj.event.start_time
        super().save_model(request, obj, form, change)


@admin.register(DailyPick)
class DailyPickAdmin(admin.ModelAdmin):
    list_display = ["user", "potd", "selection", "result", "created_at"]
    list_filter = ["result"]
    search_fields = ["user__username", "user__email"]
    raw_id_fields = ["user", "potd", "selection"]
    readonly_fields = ["created_at"]
