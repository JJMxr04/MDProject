"""Match signals — cache invalidation hooks.

Right now there's one hook: when a Match's ``end_date`` changes, the
per-match pick-popup events cache (``portal:events:match:{id}``) is
stale because the upper bound of the events query window comes from
``end_date``. Wipe it so the next popup open re-fetches from the
aggregator instead of serving an outdated 30s snapshot.
"""

from __future__ import annotations

import logging

from django.core.cache import cache
from django.db.models.signals import pre_save
from django.dispatch import receiver

from core.match.models import Match

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Match)
def invalidate_pick_events_cache(sender, instance: Match, **kwargs):
    """Drop the popup events cache when end_date moves.

    Compare against the row in the DB (if any) so we only delete when
    the value actually changes. New-row inserts skip the delete since
    there's no prior cache entry to invalidate.
    """
    if not instance.pk:
        return
    try:
        previous = Match.objects.only("end_date").get(pk=instance.pk)
    except Match.DoesNotExist:
        return
    if previous.end_date == instance.end_date:
        return
    cache_key = f"portal:events:match:{instance.pk}"
    try:
        cache.delete(cache_key)
    except Exception as exc:  # noqa: BLE001
        # Cache layer hiccup must not break the save.
        logger.warning(
            "invalidate_pick_events_cache: cache.delete(%s) failed: %s",
            cache_key, exc,
        )
