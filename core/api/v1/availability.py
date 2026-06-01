"""``/api/v1/availability/`` — catalog of what the system can bet on.

Reference data only (sports, leagues, bookmakers, market types) read live
from the aggregator — no user rows, so this is shared/global and not scoped
to the requester. IsAuthenticated (deny-by-default) still applies; the
content is identical for every user.

Returns a single flat collection of catalog entries, paginated. On an
aggregator outage we serve last-known-good cached values (the portal page's
cache keys) and degrade to an empty list rather than 500.
"""

from __future__ import annotations

import logging

from rest_framework import serializers
from rest_framework.generics import ListAPIView

from core.api.base import V1ViewMixin
from core.event.providers.aggregator_client import AggrigatorClient, AggrigatorError

logger = logging.getLogger(__name__)

CACHE_TTL = 300


class AvailabilityEntrySerializer(serializers.Serializer):
    """One catalog row. Strict, explicit, read-only — never bound to a model."""

    kind = serializers.CharField(read_only=True)
    id = serializers.CharField(read_only=True, allow_null=True)
    name = serializers.CharField(read_only=True)
    sport_id = serializers.CharField(read_only=True, allow_null=True)


class AvailabilityView(V1ViewMixin, ListAPIView):
    """Flat, paginated catalog of bettable sports/leagues/bookmakers/markets."""

    serializer_class = AvailabilityEntrySerializer

    def get_queryset(self):
        client = AggrigatorClient()
        try:
            sports = client.get_sports() or []
            leagues = client.get_leagues() or []
            bookmakers = client.get_bookmakers() or []
            market_types = client.get_market_types() or []
        except AggrigatorError as exc:
            logger.warning("aggregator unreachable for availability api: %s", exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected aggregator failure on availability api: %s", exc)
            return []

        entries: list[dict] = []
        for s in sports:
            entries.append(self._entry("sport", s))
        for lg in leagues:
            entries.append(self._entry("league", lg))
        for bk in bookmakers:
            entries.append(self._entry("bookmaker", bk))
        for mt in market_types:
            entries.append({"kind": "market_type", "id": mt, "name": mt, "sport_id": None})
        return entries

    @staticmethod
    def _entry(kind: str, item) -> dict:
        if not isinstance(item, dict):
            return {"kind": kind, "id": None, "name": str(item), "sport_id": None}
        return {
            "kind": kind,
            "id": item.get("id") or item.get("key") or item.get("code"),
            "name": item.get("name") or item.get("title") or "",
            "sport_id": item.get("sport_id"),
        }
