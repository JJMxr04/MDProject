"""Append-only audit + idempotency log for inbound aggregator webhooks.

A row per accepted delivery. The unique ``idempotency_key`` short-circuits
duplicate retries from the aggregator (plan §4.6).
"""

from __future__ import annotations

from django.db import models

from core.event.models.event import Event


class WebhookReceived(models.Model):
    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="webhook_receipts"
    )
    idempotency_key = models.CharField(max_length=128, unique=True)
    event_name = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_event_webhook_received"
        indexes = [
            # Django caps index names at 30 chars (E034).
            models.Index(
                fields=["event", "received_at"],
                name="ix_wh_recv_event_received",
            ),
        ]
