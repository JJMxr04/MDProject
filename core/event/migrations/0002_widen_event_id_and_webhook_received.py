"""Widen Event.id from 32 to 64 chars (plan §7.6) + add WebhookReceived
table for receiver-side idempotency on the new ``/sportgameodds/webhook``
endpoint.
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_event", "0001_initial"),
    ]

    operations = [
        # The aggregator's outbound webhook ships with VARCHAR(64) PKs; both
        # sides expand together. Django re-derives the FK type for any
        # column referencing Event.id from this AlterField.
        migrations.AlterField(
            model_name="event",
            name="id",
            field=models.CharField(max_length=64, primary_key=True, serialize=False),
        ),
        migrations.CreateModel(
            name="WebhookReceived",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("idempotency_key", models.CharField(max_length=128, unique=True)),
                ("event_name", models.CharField(max_length=64)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_receipts",
                        to="core_event.event",
                    ),
                ),
            ],
            options={
                "db_table": "core_event_webhook_received",
                "indexes": [
                    models.Index(
                        fields=["event", "received_at"],
                        name="ix_wh_recv_event_received",
                    ),
                ],
            },
        ),
    ]
