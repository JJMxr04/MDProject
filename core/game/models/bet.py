from django.db import models
from django.utils import timezone

from core.abstract.models import AbstractManager, AbstractModel
from core.event.models import Market, Selection


class BetManager(AbstractManager):
    def create_bet(self):
        """Empty bet — both sides start unpicked."""
        return self.create()

    def set_owner_outcome(self, bet, selection: Selection):
        bet.owner_outcome = selection
        bet.owner_decimal_odds_at_pick = selection.decimal_odds
        bet.owner_picked_at = timezone.now()
        bet.save(
            update_fields=[
                "owner_outcome",
                "owner_decimal_odds_at_pick",
                "owner_picked_at",
                "updated_at",
            ]
        )

    def set_player_2_outcome(self, bet, selection: Selection):
        bet.player_2_outcome = selection
        bet.player_2_decimal_odds_at_pick = selection.decimal_odds
        bet.player_2_picked_at = timezone.now()
        bet.save(
            update_fields=[
                "player_2_outcome",
                "player_2_decimal_odds_at_pick",
                "player_2_picked_at",
                "updated_at",
            ]
        )

    def clear_owner_outcome(self, bet):
        bet.owner_outcome = None
        bet.owner_decimal_odds_at_pick = None
        bet.owner_picked_at = None
        bet.save(
            update_fields=[
                "owner_outcome",
                "owner_decimal_odds_at_pick",
                "owner_picked_at",
                "updated_at",
            ]
        )

    def clear_player_2_outcome(self, bet):
        bet.player_2_outcome = None
        bet.player_2_decimal_odds_at_pick = None
        bet.player_2_picked_at = None
        bet.save(
            update_fields=[
                "player_2_outcome",
                "player_2_decimal_odds_at_pick",
                "player_2_picked_at",
                "updated_at",
            ]
        )


class Bet(AbstractModel):
    owner_outcome = models.ForeignKey(
        Selection,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    player_2_outcome = models.ForeignKey(
        Selection,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    # Used by the Golden Game so the system pre-picks the *market* (e.g.
    # Moneyline FULL_GAME) without choosing either side. Both players then
    # submit their own selection within this market — neither is auto-locked.
    # ``None`` for regular slots: their market is determined by the first
    # picker's choice (existing logic in Game.objects.upload_pick).
    locked_market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    owner_decimal_odds_at_pick = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )
    player_2_decimal_odds_at_pick = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )

    owner_picked_at = models.DateTimeField(null=True, blank=True)
    player_2_picked_at = models.DateTimeField(null=True, blank=True)

    # Golden Game only: stamped when the "your golden pick hit" peak
    # notification fired (plan Phase 7 #2). The atomic claim on this column
    # is the exactly-once guard — settlement replays / re-saves / the bulk
    # path re-walking the event can't re-fire it.
    golden_hit_notified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BetManager()

    class Meta:
        db_table = "core.bet"
