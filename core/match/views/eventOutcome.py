"""``event_outcomes`` — per-event markets fetch for the upload-pick popup.

Proxies to the aggregator's ``GET /v1/events/{id}`` (with markets included)
per plan §2.4.2. The aggregator side has been enriched (plan v2 portal
redesign) so:

- each ``event`` ships nested ``sport`` / ``league`` / ``home_team`` /
  ``away_team`` objects
- each ``selection`` ships an ``odds: {decimal, american, fractional}``
  envelope so the popup JS reads ``s.odds.american`` directly without any
  client-side conversion

Naming bridge: the aggregator's canonical primary key field is ``id`` on every
entity (Market.id, Selection.id) but MDProject's existing JS / DRF serializers
use ``market_id`` / ``selection_id``. We add those as aliases here at the
proxy boundary so the popup works uniformly across both code paths
(``/event/.../outcomes/`` here and ``/game/.../market/`` from
``eventMarket.py``).

URL signature: ``<str:event_id>`` (was ``<int:event_id>`` — fixed per plan
§7.7 #1; SGO eventIDs are alphanumeric strings, never ints).

Failure modes (plan §2.4.2 matrix):
- aggregator down / 5xx / timeout → 503 with a short JSON body
- aggregator 404 → 404
- aggregator returns partial data → forward as-is
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)

logger = logging.getLogger(__name__)


def _shape_for_popup(body: dict, event_id: str) -> dict:
    """Reshape the aggregator's ``EventDetailOut`` (event fields at top
    level + ``markets`` array + ``odds_meta``) into the envelope the popup JS
    expects: ``{event: {...event with event_id alias + markets aliased...},
    odds_meta}``.

    Aliases added (canonical → legacy):
      - ``event.id`` → ``event_id``
      - ``market.id`` → ``market_id``
      - ``selection.id`` → ``selection_id``
    """
    markets = body.get("markets") or []
    aliased_markets = []
    for m in markets:
        m2 = dict(m)
        m2["market_id"] = m.get("id")
        sels = []
        for s in m.get("selections") or []:
            s2 = dict(s)
            s2["selection_id"] = s.get("id")
            sels.append(s2)
        m2["selections"] = sels
        aliased_markets.append(m2)

    event_block = {k: v for k, v in body.items() if k not in ("markets", "odds_meta")}
    event_block["event_id"] = body.get("id") or event_id
    event_block["markets"] = aliased_markets

    return {
        "event": event_block,
        "odds_meta": body.get("odds_meta") or {},
    }


@require_GET
@login_required(login_url='/auth/login/')
def event_outcomes(request: HttpRequest, event_id: str) -> JsonResponse:
    if not event_id or not event_id.strip():
        return JsonResponse({"detail": "event_id required"}, status=400)

    cache_key = f"portal:events:outcomes:{event_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse(cached)

    client = AggrigatorClient()
    try:
        body = client.get_event(event_id, include_markets=True)
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for event=%s: %s", event_id, exc)
        return JsonResponse(
            {"detail": "Aggregator temporarily unavailable"},
            status=503,
        )

    if not body:
        return JsonResponse({"detail": "Event not found"}, status=404)

    response_body = _shape_for_popup(body, event_id)
    ttl = 5 if (response_body["odds_meta"] or {}).get("is_live") else 10
    cache.set(cache_key, response_body, timeout=ttl)
    return JsonResponse(response_body)
