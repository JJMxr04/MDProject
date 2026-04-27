"""Django admin for the event/odds graph.

Navigation contract:
- ``Event`` change page → inline list of all ``Market`` rows. Each row has a
  "Change" link that drills into the market's own change page.
- ``Market`` change page → inline ``Selection`` rows + an "Open event" link
  field at the top to walk back up.
- ``Selection`` change page → inline ``BookmakerSelection`` (current per-book
  quotes) and ``OddsQuote`` (price-movement history) rows + "Open market" link.

Inlines use ``show_change_link=True`` so the chain works both directions
without breadcrumbs alone.
"""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import (
    Bookmaker,
    BookmakerSelection,
    Event,
    League,
    Market,
    OddsQuote,
    Selection,
    Sport,
    Team,
)


# --- helpers ---------------------------------------------------------------


def _link(obj, label: str | None = None) -> str:
    """Render an admin change-page anchor for any model instance."""
    if obj is None:
        return "—"
    meta = obj._meta
    url = reverse(f"admin:{meta.app_label}_{meta.model_name}_change", args=[obj.pk])
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


# --- inlines ---------------------------------------------------------------


class MarketInline(admin.TabularInline):
    """Markets shown inside an Event's change page."""

    model = Market
    fk_name = "event"
    fields = ("category", "type", "scope", "line", "side", "is_live", "suspended", "last_updated")
    readonly_fields = ("category", "type", "scope", "line", "side", "is_live", "suspended", "last_updated")
    show_change_link = True
    extra = 0
    can_delete = False
    ordering = ("category", "scope", "line")

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("sport")


class SelectionInline(admin.TabularInline):
    """Selections shown inside a Market's change page."""

    model = Selection
    fk_name = "market"
    fields = (
        "type", "label", "decimal_odds", "movement", "suspended",
        "settlement_status", "settled_at", "settlement_source",
    )
    readonly_fields = (
        "type", "label", "decimal_odds", "movement", "suspended",
        "settlement_status", "settled_at", "settlement_source",
    )
    show_change_link = True
    extra = 0
    can_delete = False
    ordering = ("type",)

    def has_add_permission(self, request, obj=None):
        return False


class BookmakerSelectionInline(admin.TabularInline):
    """Per-book quotes shown inside a Selection's change page."""

    model = BookmakerSelection
    fk_name = "selection"
    fields = (
        "bookmaker", "decimal_odds", "spread", "over_under",
        "available", "last_updated_at", "deeplink",
    )
    readonly_fields = (
        "bookmaker", "decimal_odds", "spread", "over_under",
        "available", "last_updated_at", "deeplink",
    )
    show_change_link = True
    extra = 0
    can_delete = False
    ordering = ("bookmaker_id",)

    def has_add_permission(self, request, obj=None):
        return False


class OddsQuoteInline(admin.TabularInline):
    """Price-movement history shown inside a Selection's change page."""

    model = OddsQuote
    fk_name = "selection"
    fields = ("decimal_odds", "captured_at")
    readonly_fields = ("decimal_odds", "captured_at")
    show_change_link = False
    extra = 0
    can_delete = False
    ordering = ("-captured_at",)
    max_num = 50

    def has_add_permission(self, request, obj=None):
        return False


# --- admin classes ---------------------------------------------------------


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "active", "created", "updated"]
    list_filter = ["active"]
    search_fields = ["id", "name"]
    readonly_fields = ["created", "updated"]


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = [
        "id", "sport", "name", "active",
        "refresh_cadence_minutes", "last_refreshed_at",
    ]
    list_filter = ["active", "sport"]
    search_fields = ["id", "name", "short_name"]
    readonly_fields = ["created", "updated", "last_refreshed_at"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "id", "league", "season_label", "start_time", "status_type",
        "home_team", "away_team", "home_score", "away_score", "winner",
    ]
    list_filter = ["league", "sport", "status_type", "is_live", "is_finalized", "completed"]
    search_fields = [
        "id", "season_label", "winner",
        "home_team__name_long", "away_team__name_long",
    ]
    readonly_fields = [
        "id", "public_id", "created", "updated",
        "home_team_link", "away_team_link", "league_link",
        "refresh_button",
    ]
    inlines = [MarketInline]
    fieldsets = (
        ("Identity", {"fields": ("id", "public_id", "type", "season_label")}),
        ("API refresh", {"fields": ("refresh_button",)}),
        ("Hierarchy", {"fields": ("league_link", "league", "sport", "home_team_link", "away_team_link", "home_team", "away_team")}),
        ("Status", {"fields": ("status_type", "status_display", "current_period_id", "is_live", "is_finalized", "completed", "feed_locked", "start_time")}),
        ("Result", {"fields": ("home_score", "away_score", "winner_code", "winner")}),
        ("Bookkeeping", {"fields": ("last_provider_refresh_at", "created", "updated")}),
    )
    actions = ["refresh_from_api", "force_finish_and_settle"]

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/refresh-from-api/",
                self.admin_site.admin_view(self.refresh_single_view),
                name="core_event_event_refresh_from_api",
            ),
        ]
        return custom + urls

    def refresh_single_view(self, request, object_id):
        """Single-event refresh, hit from the in-form button."""
        from core.event.odds.service import get_event_odds
        from core.event.providers import SportsGameOddsError

        ev = Event.objects.filter(pk=object_id).first()
        if ev is None:
            messages.error(request, f"Event {object_id} not found")
            return redirect("admin:core_event_event_changelist")
        try:
            result = get_event_odds(ev, force=True)
        except SportsGameOddsError as exc:
            messages.error(request, f"API error: {exc}")
        else:
            if result.stale:
                messages.warning(
                    request,
                    "Refresh returned no data — API empty, cap hit, or quota exhausted.",
                )
            else:
                refreshed = result.event or ev
                if refreshed.is_finalized:
                    messages.success(
                        request,
                        f"Refreshed + settled. {refreshed.home_team} {refreshed.home_score} – "
                        f"{refreshed.away_score} {refreshed.away_team}",
                    )
                else:
                    messages.info(
                        request,
                        f"Refreshed. Status: {refreshed.status_type} "
                        f"(API has not marked this event as finalized yet).",
                    )
        return redirect("admin:core_event_event_change", object_id)

    @admin.display(description="Pull latest from API")
    def refresh_button(self, obj):
        if obj.pk is None:
            return "Save the event first."
        url = reverse("admin:core_event_event_refresh_from_api", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" '
            'style="background:#417690;color:#fff;padding:6px 12px;border-radius:4px;'
            'text-decoration:none;display:inline-block;">'
            '↻ Refresh from API now</a>'
            '<p class="help" style="margin-top:6px;">'
            'Forces an SGO fetch (bypasses TTL + cap). If the API reports the event '
            'as finalized, settlement runs and matches are scored automatically — '
            "even if the event's <code>start_time</code> is in the future."
            '</p>',
            url,
        )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "league", "sport", "home_team", "away_team",
        )

    # ------ Drill-up links ------

    @admin.display(description="League (open)")
    def league_link(self, obj):
        return _link(obj.league)

    @admin.display(description="Home team (open)")
    def home_team_link(self, obj):
        return _link(obj.home_team)

    @admin.display(description="Away team (open)")
    def away_team_link(self, obj):
        return _link(obj.away_team)

    # ------ Save-time settlement cascade ------

    def save_model(self, request, obj, form, change):
        """When status_type flips to 'finished' (or scores change on an
        already-finished event), run the same cascade ingest fires:

        1. Derive ``winner_code`` / ``winner`` / ``completed`` / ``is_finalized``
           from the current home/away score so the row is internally consistent.
        2. ``settle_event`` to grade pending selections via the COMPUTED path.
        3. Propagate to any Match holding bets on this event.

        Lets ops finalize an event manually — even one whose ``start_time`` is
        in the future — and have everything downstream calculate cleanly.
        """
        previous = None
        if change:
            previous = Event.objects.filter(pk=obj.pk).only(
                "status_type", "home_score", "away_score",
            ).first()

        # Auto-derive consistent state when status is flipped to 'finished'
        if obj.status_type == "finished":
            if obj.home_score is not None and obj.away_score is not None:
                if obj.home_score > obj.away_score:
                    obj.winner_code = 1
                elif obj.away_score > obj.home_score:
                    obj.winner_code = 2
                else:
                    obj.winner_code = 3
                obj.winner = (
                    obj.home_team.name_long if obj.winner_code == 1 and obj.home_team
                    else obj.away_team.name_long if obj.winner_code == 2 and obj.away_team
                    else "Draw" if obj.winner_code == 3 else None
                )
            obj.is_finalized = True
            obj.completed = True

        super().save_model(request, obj, form, change)

        became_finished = (
            obj.status_type == "finished"
            and (previous is None or previous.status_type != "finished")
        )
        score_changed = (
            obj.status_type == "finished"
            and previous is not None
            and (previous.home_score != obj.home_score
                 or previous.away_score != obj.away_score)
        )
        if became_finished or score_changed:
            from core.event.odds.settlement import settle_event

            n = settle_event(obj)
            messages.success(
                request,
                f"Settled event {obj.id} — {n} selection(s) updated. "
                f"{obj.home_team} {obj.home_score} – {obj.away_score} {obj.away_team}",
            )

    @admin.action(description="Refresh from API (re-fetch + settle if finalized)")
    def refresh_from_api(self, request, queryset):
        """Pull the latest payload for each selected event from SportsGameOdds
        (or the simulator) and re-ingest. The SGO call goes through
        ``get_event_odds(event, force=True)`` so:

        - Per-event TTL is bypassed (force=True)
        - Per-event monthly cap is bypassed (only when EVENTS_DEBUG_FORCE_FRESH=True)
        - If the API marks the event ``finalized``, the existing pipeline
          (``upsert_from_spec`` → ``settle_event`` + ``write_markets`` →
          ``grade_event``) settles every PENDING selection and walks the
          matches via ``propagate_to_matches`` — automatically.

        Works regardless of the event's ``start_time`` (the API call uses the
        eventID directly, not a date window).
        """
        from core.event.odds.service import get_event_odds
        from core.event.providers import SportsGameOddsError

        refreshed = 0
        finalized = 0
        stale = 0
        errors = []
        for ev in queryset:
            try:
                result = get_event_odds(ev, force=True)
            except SportsGameOddsError as exc:
                errors.append((ev.id, str(exc)))
                continue
            if result.stale:
                stale += 1
                continue
            refreshed += 1
            # `result.event` is the post-refresh row (or the original instance).
            if (result.event or ev).is_finalized:
                finalized += 1

        if refreshed:
            messages.success(
                request,
                f"Refreshed {refreshed} event(s) from API "
                f"({finalized} finalized → settlement ran).",
            )
        if stale:
            messages.warning(
                request,
                f"{stale} event(s) returned no data (cap hit, API empty, or quota exhausted).",
            )
        for eid, msg in errors:
            messages.error(request, f"{eid}: {msg}")

    @admin.action(description="Force finish + settle (uses current scores)")
    def force_finish_and_settle(self, request, queryset):
        """Bulk variant: flip status to 'finished' on selected events that
        already have home/away scores filled in. Skips events without scores
        because we can't decide a winner.
        """
        from core.event.odds.settlement import settle_event

        finalized = 0
        skipped = 0
        for ev in queryset:
            if ev.home_score is None or ev.away_score is None:
                skipped += 1
                continue
            ev.status_type = "finished"
            ev.is_finalized = True
            ev.completed = True
            if ev.home_score > ev.away_score:
                ev.winner_code = 1
            elif ev.away_score > ev.home_score:
                ev.winner_code = 2
            else:
                ev.winner_code = 3
            ev.winner = (
                ev.home_team.name_long if ev.winner_code == 1 and ev.home_team
                else ev.away_team.name_long if ev.winner_code == 2 and ev.away_team
                else "Draw" if ev.winner_code == 3 else None
            )
            ev.save()
            settle_event(ev)
            finalized += 1
        if finalized:
            messages.success(request, f"Finalized + settled {finalized} event(s).")
        if skipped:
            messages.warning(
                request,
                f"Skipped {skipped} event(s) without home_score/away_score. "
                "Set scores first, then re-run this action.",
            )


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["id", "name_long", "name_short", "league", "sport"]
    list_filter = ["league", "sport"]
    search_fields = ["id", "team_id", "name_long", "name_short", "name_medium"]
    readonly_fields = ["id", "public_id", "created", "updated", "league_link"]
    fieldsets = (
        ("Identity", {"fields": ("id", "public_id", "team_id")}),
        ("Hierarchy", {"fields": ("league_link", "league", "sport")}),
        ("Names", {"fields": ("name_long", "name_medium", "name_short", "stat_entity_id")}),
        ("Branding", {"fields": ("primary_color", "secondary_color", "primary_contrast", "secondary_contrast", "logo_url")}),
        ("Bookkeeping", {"fields": ("created", "updated")}),
    )

    @admin.display(description="League (open)")
    def league_link(self, obj):
        return _link(obj.league)


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = [
        "id", "event", "category", "type", "scope", "line",
        "is_live", "suspended", "last_updated",
    ]
    list_filter = ["category", "scope", "is_live", "suspended", "sport"]
    search_fields = ["id", "event__id", "type"]
    readonly_fields = [
        "id", "provider", "provider_market_id", "provider_choice_group",
        "created", "updated", "event_link", "subject_team_link",
    ]
    inlines = [SelectionInline]
    fieldsets = (
        ("Identity", {"fields": ("id", "type", "category", "scope", "line", "side")}),
        ("Hierarchy", {"fields": ("event_link", "event", "sport", "subject_team_link", "subject_team")}),
        ("State", {"fields": ("is_live", "suspended", "last_updated")}),
        ("Provider", {"fields": ("provider", "provider_market_id", "provider_choice_group")}),
        ("Bookkeeping", {"fields": ("created", "updated")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "event", "sport", "subject_team",
        )

    @admin.display(description="Open event")
    def event_link(self, obj):
        return _link(obj.event)

    @admin.display(description="Subject team (open)")
    def subject_team_link(self, obj):
        return _link(obj.subject_team)


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = [
        "id", "market", "type", "label", "decimal_odds", "movement",
        "suspended", "settlement_status", "settled_at", "settlement_source",
    ]
    list_filter = ["settlement_status", "settlement_source", "type", "suspended"]
    search_fields = ["id", "market__id", "label"]
    readonly_fields = [
        "id", "created", "updated", "market_link", "event_link",
    ]
    inlines = [BookmakerSelectionInline, OddsQuoteInline]
    fieldsets = (
        ("Identity", {"fields": ("id", "type", "label")}),
        ("Hierarchy", {"fields": ("event_link", "market_link", "market")}),
        ("Pricing", {"fields": ("decimal_odds", "opening_decimal_odds", "movement", "suspended")}),
        ("Settlement", {"fields": ("settlement_status", "settled_at", "settlement_source")}),
        ("Bookkeeping", {"fields": ("created", "updated")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "market", "market__event",
        )

    @admin.display(description="Open market")
    def market_link(self, obj):
        return _link(obj.market)

    @admin.display(description="Open event")
    def event_link(self, obj):
        return _link(obj.market.event if obj.market_id else None)


@admin.register(OddsQuote)
class OddsQuoteAdmin(admin.ModelAdmin):
    list_display = ["id", "selection", "decimal_odds", "captured_at"]
    list_filter = ["captured_at"]
    search_fields = ["selection__id"]
    readonly_fields = ["id", "selection", "decimal_odds", "captured_at", "selection_link"]
    fieldsets = (
        ("Identity", {"fields": ("id", "decimal_odds", "captured_at")}),
        ("Hierarchy", {"fields": ("selection_link", "selection")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("selection", "selection__market")

    @admin.display(description="Open selection")
    def selection_link(self, obj):
        return _link(obj.selection)


@admin.register(Bookmaker)
class BookmakerAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "active"]
    list_filter = ["active"]
    search_fields = ["id", "name"]


@admin.register(BookmakerSelection)
class BookmakerSelectionAdmin(admin.ModelAdmin):
    list_display = [
        "selection", "bookmaker", "decimal_odds", "spread", "over_under",
        "available", "last_updated_at",
    ]
    list_filter = ["bookmaker", "available"]
    search_fields = ["selection__id", "bookmaker__id"]
    readonly_fields = [
        "created", "updated",
        "selection_link", "bookmaker_link",
    ]
    fieldsets = (
        ("Pricing", {"fields": ("decimal_odds", "spread", "over_under", "available", "deeplink", "last_updated_at")}),
        ("Hierarchy", {"fields": ("selection_link", "selection", "bookmaker_link", "bookmaker")}),
        ("Bookkeeping", {"fields": ("created", "updated")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("selection", "bookmaker")

    @admin.display(description="Open selection")
    def selection_link(self, obj):
        return _link(obj.selection)

    @admin.display(description="Open bookmaker")
    def bookmaker_link(self, obj):
        return _link(obj.bookmaker)
