"""``event_outcomes`` — per-event markets fetch for the upload-pick popup.

After the aggregator cutover (plan §2.4.2), this view proxies to the
aggregator's authoritative ``GET /v1/events/{id}/markets`` instead of reading
from MDProject's local DB. The local DB only has events the user has already
picked; the popup needs the full live catalog.

URL signature: ``<str:event_id>`` (was ``<int:event_id>`` — fixed per plan
§7.7 #1; SGO eventIDs are alphanumeric strings, never ints).

Failure modes (plan §2.4.2 matrix):
- aggregator down / 5xx / timeout → 503 with a short JSON body
- aggregator 404 → 404
- aggregator returns partial data → forward as-is
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)

logger = logging.getLogger(__name__)


@require_GET
@login_required(login_url='/auth/login/')
def event_outcomes(request: HttpRequest, event_id: str) -> JsonResponse:
    if not event_id or not event_id.strip():
        return JsonResponse({"detail": "event_id required"}, status=400)

    if not getattr(settings, "USE_AGGRIGATOR", False):
        # Pre-cutover fallback: legacy local-DB path. Kept so flipping
        # USE_AGGRIGATOR=False is a clean rollback (plan §9 / §2-phasing).
        from django.shortcuts import get_object_or_404
        from core.event.models import Event
        from core.event.serializers.event import EventWithMarketsSerializer
        event = get_object_or_404(Event, id=event_id)
        return JsonResponse(
            {"event": EventWithMarketsSerializer(event).data},
        )

    cache_key = f"portal:events:outcomes:{event_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    client = AggrigatorClient()
    try:
        body = client.get_event_markets(event_id)
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for event=%s: %s", event_id, exc)
        return JsonResponse(
            {"detail": "Aggregator temporarily unavailable"},
            status=503,
        )

    if not body:
        return JsonResponse({"detail": "Event not found"}, status=404)

    # Reshape: the popup's existing JS expects ``{event: {markets: [...]}}``.
    # Aggregator returns ``{markets: [...], odds_meta: {...}}``. Wrap it.
    response_body = {
        "event": {
            "event_id": event_id,
            "markets": body.get("markets") or [],
        },
        "odds_meta": body.get("odds_meta", {}),
    }
    # Pick TTL by liveness — short for live, longer for pre-event.
    ttl = 5 if (response_body["odds_meta"] or {}).get("is_live") else 10
    cache.set(cache_key, response_body, timeout=ttl)
    return JsonResponse(response_body)
