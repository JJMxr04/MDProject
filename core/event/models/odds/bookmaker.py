"""Per-bookmaker quote storage.

The fair-odds row on ``Selection`` is the canonical price for settlement and
internal math. Per-book entries are display-only — they power "DraftKings has
-150, FanDuel has -145" UI and the deeplinks that send users to the book.
"""

from django.db import models


class Bookmaker(models.Model):
    id = models.CharField(max_length=32, primary_key=True)  # SGO bookmakerID
    name = models.CharField(max_length=64)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = "core_bookmaker"
        ordering = ["id"]

    def __str__(self):
        return self.name or self.id


class BookmakerSelection(models.Model):
    """One per ``(Selection, Bookmaker)`` — the bookmaker's *current* quote.

    Updated in place on every odds refresh; no time-series. If we want
    per-book movement history later, mirror this into a sibling table.
    """

    selection = models.ForeignKey(
        "core_event.Selection",
        on_delete=models.CASCADE,
        related_name="by_book",
    )
    bookmaker = models.ForeignKey(
        Bookmaker, on_delete=models.PROTECT, related_name="quotes"
    )

    decimal_odds = models.DecimalField(
        max_digits=8, decimal_places=4, null=True, blank=True
    )
    spread = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    over_under = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    available = models.BooleanField(default=True)
    deeplink = models.URLField(max_length=500, blank=True)
    last_updated_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_bookmaker_selection"
        unique_together = [("selection", "bookmaker")]
        indexes = [
            models.Index(fields=["selection", "available"]),
            models.Index(fields=["bookmaker", "available"]),
        ]

    def __str__(self):
        return f"{self.bookmaker_id} → {self.selection_id} = {self.decimal_odds}"
