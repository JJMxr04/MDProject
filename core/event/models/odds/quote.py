from django.db import models


class OddsQuote(models.Model):
    """Append-only line-movement history.

    A new row is inserted only when a Selection's price actually changes — so
    this table functions as a compact time series for movement charts.
    """

    id = models.BigAutoField(primary_key=True)
    selection = models.ForeignKey(
        "core_event.Selection", on_delete=models.CASCADE, related_name="quotes"
    )
    decimal_odds = models.DecimalField(max_digits=8, decimal_places=4)
    captured_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "core_odds_quote"
        indexes = [models.Index(fields=["selection", "captured_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["selection", "captured_at"],
                name="uq_quote_selection_captured",
            )
        ]
