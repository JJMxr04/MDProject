"""``/api/v1/analytics/events/<event_id>/`` — catalog/event analytics.

Paywalled mirror of the inline analytics block on the portal event-detail
page: form-into-match + H2H (context), season-to-date (historical-stats),
and — for not-yet-finalized events — model probabilities + live odds.

Not user-owned data (it's catalog analytics for an event), so no cross-user
scoping. But it requires auth (``IsAuthenticated`` from the mixin) AND
entitlement (``IsPaid``).

Reuses the portal's ``aggrigator_client`` helpers — the same HTTP calls the
event-detail view makes — rather than reimplementing them. Each helper returns
an empty dict on transport failure; when every section comes back empty we
treat it as an upstream outage and surface a 502 ``upstream_unavailable``
through the envelope instead of a misleading empty 200.
"""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api.base import V1ViewMixin
from core.api.permissions import IsPaid
from core.portal.services import aggrigator_client


class UpstreamUnavailable(APIException):
    """Aggregator outage -> 502 ``upstream_unavailable`` via the envelope."""

    status_code = 502
    default_detail = "Analytics provider is temporarily unavailable."


class EventAnalyticsSerializer(serializers.Serializer):
    """Explicit, read-only shape — never echoes arbitrary upstream fields."""

    event_id = serializers.CharField(read_only=True)
    is_finalized = serializers.BooleanField(read_only=True)
    form_into_match = serializers.DictField(read_only=True)
    form_detail = serializers.DictField(read_only=True)
    h2h_last_5 = serializers.ListField(read_only=True)
    h2h_aggregate = serializers.DictField(read_only=True)
    historical_stats = serializers.DictField(read_only=True)
    # Upcoming-only model-vs-market block; empty for finalized events.
    model_prob = serializers.DictField(read_only=True)
    live_odds = serializers.DictField(read_only=True)


class EventAnalyticsView(V1ViewMixin, APIView):
    """Aggregator analytics for one event. Auth + entitlement required."""

    permission_classes = V1ViewMixin.permission_classes + [IsPaid]
    pagination_class = None

    def get(self, request, event_id: str):
        # Shared catalog data — the client's service key covers auth
        # (plan §6.4); entitlement was already enforced by IsPaid above.
        context = aggrigator_client.event_context(event_id)
        historical_stats = aggrigator_client.event_historical_stats(event_id)
        probabilities = aggrigator_client.event_probabilities(event_id)
        live_odds = aggrigator_client.event_live_odds(event_id)

        # Each helper returns {} on transport failure; all-empty means the
        # upstream is down (a valid event always carries at least one block).
        if not (context or historical_stats or probabilities or live_odds):
            raise UpstreamUnavailable()

        is_finalized = bool(historical_stats.get("is_finalized")) or not probabilities

        payload = {
            "event_id": event_id,
            "is_finalized": is_finalized,
            "form_into_match": context.get("form_into_match") or {},
            "form_detail": context.get("form_detail") or {},
            "h2h_last_5": context.get("h2h_last_5") or [],
            "h2h_aggregate": context.get("h2h_aggregate") or {},
            "historical_stats": historical_stats or {},
            "model_prob": probabilities or {},
            "live_odds": live_odds or {},
        }
        return Response(EventAnalyticsSerializer(payload).data)
