from django.contrib import admin
from django.db.models import Count

from core.event.odds.humanize import humanize_selection
from core.potd.models import DailyPick, PickOfDay


class DailyPickInline(admin.TabularInline):
    """Everyone's picks for the day, right on the PickOfDay page."""
    model = DailyPick
    extra = 0
    can_delete = False
    fields = ["user", "picked", "result", "created_at"]
    readonly_fields = ["user", "picked", "result", "created_at"]
    ordering = ["-created_at"]

    def picked(self, obj):
        return humanize_selection(obj.selection)

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "user", "selection", "selection__market",
            "selection__market__event",
            "selection__market__event__home_team",
            "selection__market__event__away_team",
        )


@admin.register(PickOfDay)
class PickOfDayAdmin(admin.ModelAdmin):
    """Manual-curation override: create/replace a day's pick here and the
    nightly cron will leave it alone (it never overwrites an existing row).
    Use raw event/market ids; lock_time defaults to the event kickoff."""
    list_display = ["date", "event", "market", "lock_time", "manually_curated", "pick_count"]
    list_filter = ["manually_curated"]
    search_fields = ["event__id", "event__home_team__name_long", "event__away_team__name_long"]
    raw_id_fields = ["event", "market"]
    readonly_fields = ["created_at", "pick_breakdown"]
    ordering = ["-date"]
    inlines = [DailyPickInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_pick_count=Count("picks"))

    @admin.display(description="Picks", ordering="_pick_count")
    def pick_count(self, obj):
        return obj._pick_count

    @admin.display(description="Pick breakdown")
    def pick_breakdown(self, obj):
        """Per-selection tally — how the crowd split."""
        rows = (
            obj.picks.values("selection_id", "selection__label", "selection__type")
            .annotate(n=Count("id"))
            .order_by("-n")
        )
        if not rows:
            return "No picks yet."
        return " · ".join(
            f"{r['selection__type'] or r['selection__label']}: {r['n']}"
            for r in rows
        )

    def save_model(self, request, obj, form, change):
        # Anything touched by a human in the admin counts as curated.
        obj.manually_curated = True
        if not obj.lock_time and obj.event and obj.event.start_time:
            obj.lock_time = obj.event.start_time
        super().save_model(request, obj, form, change)


@admin.register(DailyPick)
class DailyPickAdmin(admin.ModelAdmin):
    list_display = ["user", "potd", "picked", "result", "created_at"]
    list_filter = ["result"]
    search_fields = ["user__username", "user__email"]
    raw_id_fields = ["user", "potd", "selection"]
    readonly_fields = ["created_at"]

    def picked(self, obj):
        return humanize_selection(obj.selection)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "user", "potd", "selection", "selection__market",
            "selection__market__event",
            "selection__market__event__home_team",
            "selection__market__event__away_team",
        )
