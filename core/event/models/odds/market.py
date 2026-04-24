from django.db import models


class MarketCategory(models.TextChoices):
    MONEYLINE = "MONEYLINE"
    SPREAD = "SPREAD"
    TOTAL = "TOTAL"
    PROPS_GAME = "PROPS_GAME"
    PROPS_TEAM = "PROPS_TEAM"


class MarketScope(models.TextChoices):
    FULL_GAME = "FULL_GAME"
    H1 = "H1"
    H2 = "H2"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    OVERTIME = "OVERTIME"
    PERIOD_N = "PERIOD_N"
    # Hockey regulation periods + shootout
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    SHOOTOUT = "SHOOTOUT"


class Market(models.Model):
    """One normalized betting market for an event.

    Primary key is a deterministic string (see `core.event.odds.normalize.build_market_id`)
    so upserts are idempotent and the Flutter client can diff market lists cheaply.
    """

    id = models.CharField(max_length=64, primary_key=True)
    event = models.ForeignKey(
        "core_event.Event", on_delete=models.CASCADE, related_name="markets"
    )
    sport = models.ForeignKey("core_event.Sport", on_delete=models.PROTECT)

    category = models.CharField(
        max_length=16, choices=MarketCategory.choices, db_index=True
    )
    type = models.CharField(max_length=48, db_index=True)
    scope = models.CharField(
        max_length=16, choices=MarketScope.choices, default=MarketScope.FULL_GAME
    )
    line = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    side = models.CharField(max_length=8, blank=True)

    provider = models.CharField(max_length=32, default="sofascore")
    provider_market_id = models.BigIntegerField(db_index=True)
    provider_choice_group = models.CharField(max_length=16, blank=True)

    subject_team = models.ForeignKey(
        "core_event.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    is_live = models.BooleanField(default=False)
    suspended = models.BooleanField(default=False)
    last_updated = models.DateTimeField(db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_market"
        indexes = [
            models.Index(fields=["event", "category", "scope"]),
            models.Index(fields=["sport", "category", "is_live"]),
            models.Index(fields=["event", "type"]),
        ]

    def __str__(self):
        return f"{self.type} @ {self.scope}" + (
            f" line={self.line}" if self.line is not None else ""
        )
