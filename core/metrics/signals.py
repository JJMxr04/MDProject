"""session_start tracking — one event per user per (local) day.

Hooked on ``user_logged_in``. Session cookies outlive a day, so a single
login can cover many visits — that's fine for v1: D1/D7 retention only
needs "did they come back and authenticate", and the portal's session
age forces re-login often enough. Daily dedupe keeps repeated logins
(e.g. two devices) from inflating active-day counts.
"""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone

from core.metrics.models import ProductEvent, track


@receiver(user_logged_in)
def track_session_start(sender, request, user, **kwargs):
    today = timezone.localdate()
    if ProductEvent.objects.filter(
        user=user, name="session_start", created_at__date=today,
    ).exists():
        return
    track(user, "session_start")
