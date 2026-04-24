from django.contrib import admin

from .models import Bet, Game


@admin.register(Bet)
class BetAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "owner_outcome",
        "player_2_outcome",
        "owner_decimal_odds_at_pick",
        "player_2_decimal_odds_at_pick",
        "created_at",
        "updated_at",
    ]
    list_filter = []
    search_fields = [
        "owner_outcome__label",
        "player_2_outcome__label",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["id", "match", "owner", "player_2", "is_golden", "slot", "event"]
    list_filter = ["is_golden"]
    search_fields = [
        "owner__username",
        "player_2__username",
        "match__id",
        "event__id",
    ]
    readonly_fields = ["id", "match", "owner", "player_2", "is_golden", "slot", "event", "bet"]
