from django.contrib import admin

from .models import Event, Market, OddsQuote, Selection, Sport, Team


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "sport",
        "tournament_name",
        "start_time",
        "status_type",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "winner",
    ]
    list_filter = ["sport", "status_type", "tournament_name", "completed"]
    search_fields = [
        "id",
        "slug",
        "tournament_name",
        "winner",
        "home_team__name",
        "away_team__name",
    ]
    readonly_fields = [
        "id",
        "public_id",
        "created",
        "updated",
        "scores_payload",
        "status_code",
    ]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "short_name", "name_code", "sport", "country_alpha2"]
    list_filter = ["sport", "gender", "national"]
    search_fields = ["id", "name", "slug", "short_name", "name_code"]
    readonly_fields = ["id", "public_id", "created", "updated"]


@admin.register(Sport)
class SportAdmin(admin.ModelAdmin):
    list_display = ["id", "slug", "name", "active", "created", "updated"]
    list_filter = ["active"]
    search_fields = ["id", "slug", "name"]
    readonly_fields = ["created", "updated"]


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ["id", "event", "category", "type", "scope", "line", "is_live", "suspended", "last_updated"]
    list_filter = ["category", "scope", "type", "is_live", "suspended", "sport"]
    search_fields = ["id", "event__id", "type"]
    readonly_fields = ["id", "provider", "provider_market_id", "provider_choice_group", "created", "updated"]


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "market",
        "type",
        "label",
        "decimal_odds",
        "movement",
        "suspended",
        "settlement_status",
        "settled_at",
        "settlement_source",
    ]
    list_filter = ["settlement_status", "settlement_source", "type", "suspended"]
    search_fields = ["id", "market__id", "label"]
    readonly_fields = ["id", "created", "updated"]


@admin.register(OddsQuote)
class OddsQuoteAdmin(admin.ModelAdmin):
    list_display = ["id", "selection", "decimal_odds", "captured_at"]
    list_filter = ["captured_at"]
    search_fields = ["selection__id"]
    readonly_fields = ["id", "selection", "decimal_odds", "captured_at"]
