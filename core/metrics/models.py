"""In-house product analytics (roadmap Phase 3 §3, decision D-3).

One append-only table + one helper. No third-party analytics — GlitchTip
is errors-only and the aggregator never sees page views, so the loop
metrics (D1/D7 retention, picks/user/week, both-players-return) have to
be computed from rows we own. Queryable in SQL forever.

Taxonomy v1 (plan roadmap Phase 3): session_start (daily-deduped),
pick_made, match_created, match_accepted, match_completed, invite_sent,
invite_accepted, rematch_clicked (Phase 5), paywall_viewed,
paywall_upgrade_clicked, checkout_started, checkout_completed,
potd_picked (Phase 6).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class ProductEvent(models.Model):
    # SET_NULL so deleting a user keeps the aggregate history (counts,
    # funnels) intact — the row just becomes anonymous.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="product_events",
    )
    name = models.CharField(max_length=64, db_index=True)
    props = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["name", "created_at"]),
            models.Index(fields=["user", "name", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} @ {self.created_at:%Y-%m-%d %H:%M} ({self.user_id or 'anon'})"


def track(user, name, **props):
    """Fire-and-forget product-event write. Swallows every failure — a
    metrics hiccup must never break a pick, a checkout, or a settlement
    path. ``user`` may be None (system events) or an AnonymousUser."""
    try:
        if user is not None and not getattr(user, "pk", None):
            user = None  # AnonymousUser → anonymous event
        ProductEvent.objects.create(user=user, name=name, props=props or {})
    except Exception:  # noqa: BLE001
        logger.exception("metrics.track(%s) failed", name)
