"""Ranking signals.

Every user should own a ``PlayerProgress`` row from signup so the portal can
always show a level / XP bar (level 1, 0 XP) instead of a blank widget — the
engine otherwise only creates the row lazily on first ranked activity, which
left existing users and brand-new signups with nothing to display.

Existing users are backfilled by migration ``core_ranking.0004``; this signal
covers everyone created after it. Mirrors the billing FREE-Subscription
pattern (``core/billing/signals.py``).
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.ranking.models import PlayerProgress
from core.user.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def ensure_progress_on_signup(sender, instance, created, **kwargs):
    if not created:
        return  # only on the original INSERT, not later profile saves
    try:
        PlayerProgress.objects.get_or_create(user=instance)
    except Exception:
        # Never crash the signup transaction over a progress row — it'll be
        # created lazily by the engine on the user's first ranked activity.
        logger.exception("failed to create PlayerProgress for %s", instance.pk)
