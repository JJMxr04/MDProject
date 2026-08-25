"""Provider factory.

Honors the comment that's been here since the SGO client landed: when a
separate data-aggregator service ships, the swap is a one-file change.

Today the factory dispatches based on settings:

- ``USE_AGGRIGATOR=True`` → returns an ``AggrigatorClient`` (HTTP to the new
  aggregator at ``AGGRIGATOR_BASE_URL``)
- otherwise → legacy direct ``SportsGameOddsClient``

During the cutover both code paths exist; flipping the
flag in env is the cutover.
"""

from __future__ import annotations

from django.conf import settings

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)
from core.event.sportsgameodds import (
    QuotaExceeded,
    SportsGameOddsClient,
    SportsGameOddsError,
)

__all__ = [
    "get_events_client",
    "SportsGameOddsError",
    "QuotaExceeded",
    "AggrigatorClient",
    "AggrigatorError",
]


def get_events_client():
    """Return the configured events provider client.

    Reads ``settings.USE_AGGRIGATOR`` (default ``False`` so existing deploys
    keep working until they flip the flag explicitly).
    """
    if getattr(settings, "USE_AGGRIGATOR", False):
        return AggrigatorClient()
    return SportsGameOddsClient()
