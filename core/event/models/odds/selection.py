from django.db import models


class SelectionType(models.TextChoices):
    HOME = "HOME"
    AWAY = "AWAY"
    DRAW = "DRAW"
    OVER = "OVER"
    UNDER = "UNDER"
    YES = "YES"
    NO = "NO"
    EVEN = "EVEN"
    ODD = "ODD"
    # Soccer double-chance: stored as the literal labels
    DC_1X = "1X"
    DC_X2 = "X2"
    DC_12 = "12"
    NO_GOAL = "NO_GOAL"
    CUSTOM = "CUSTOM"


class SettlementStatus(models.TextChoices):
    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    PUSH = "PUSH"
    VOID = "VOID"


class SettlementSource(models.TextChoices):
    PROVIDER = "PROVIDER"   # graded from SGO ``score`` per odd
    COMPUTED = "COMPUTED"   # derived from event scores via settlement.py
    MANUAL = "MANUAL"       # admin override — never auto-overwritten


class Selection(models.Model):
    """One betting choice inside a market.

    PK is synthesized from ``f"{market_id}:{statEntityID}-{sideID}"`` so
    upserts are idempotent across refreshes.
    """

    id = models.CharField(max_length=160, primary_key=True)
    market = models.ForeignKey(
        "core_event.Market", on_delete=models.CASCADE, related_name="selections"
    )
    type = models.CharField(max_length=16, choices=SelectionType.choices)
    label = models.CharField(max_length=128)
    suspended = models.BooleanField(default=False)

    # Latest price, denormalized from OddsQuote for fast list reads.
    decimal_odds = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    opening_decimal_odds = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )
    movement = models.SmallIntegerField(default=0)  # -1, 0, +1

    settlement_status = models.CharField(
        max_length=8,
        choices=SettlementStatus.choices,
        default=SettlementStatus.PENDING,
        db_index=True,
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    settlement_source = models.CharField(
        max_length=16,
        choices=SettlementSource.choices,
        blank=True,
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = "core_selection"
        indexes = [
            models.Index(fields=["market", "type"]),
            models.Index(fields=["settlement_status", "market"]),
        ]

    def __str__(self):
        return f"{self.type} {self.decimal_odds} ({self.label})"
