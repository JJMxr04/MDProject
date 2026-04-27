"""Provider factory.

Today: SportsGameOdds direct.

Future: when a separate data-aggregator service ships, replace the body of
``get_events_client`` with a settings-driven dispatch that returns an
``AggregatorClient`` with the same surface (``get_events``, ``get_event``,
``get_account_usage``, ``get_sports``, ``get_leagues``, ``get_teams``).

Callers should always import via this factory rather than instantiating
``SportsGameOddsClient`` directly — that's the contract that makes the future
swap a one-file change.
"""

from core.event.sportsgameodds import (
    QuotaExceeded,
    SportsGameOddsClient,
    SportsGameOddsError,
)

__all__ = ["get_events_client", "SportsGameOddsError", "QuotaExceeded"]


def get_events_client():
    """Returns the configured events provider client."""
    return SportsGameOddsClient()
