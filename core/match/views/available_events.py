"""``available_events_for_match`` — server-side helper for the pick popup.

Returns the catalog of events a user can pick from for one match's window.
Source-of-truth is the aggregator's ``GET /v1/events`` (plan §2.4.2). Two
callers:

- ``my_match_detail_view`` calls ``build_available_events(match)`` to populate
  the JSON island at template line 162.
- A standalone JSON endpoint (URL name ``portal-available-events-for-match``)
  is exposed for HTMX / fetch-based callers.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)
from core.match.decorators import player_in_match_required
from core.match.models import Match

logger = logging.getLogger(__name__)


# Owner-side deadline: pick must be ≥ 8h before event start (per
# Game.objects.upload_pick rules / api-switch/game-match-audit-plan.md §5.1).
OWNER_DEADLINE_BUFFER = timedelta(hours=8)
CACHE_TTL = 30  # seconds; matches plan §2.4.2 table


def _shape_for_popup(item: dict) -> dict:
    """Tiny adapter — popup JS uses ``event_id`` everywhere; aggregator's
    schema field is ``id``. Add the alias; leave the rest of the (now-enriched)
    shape alone — sport/league/home_team/away_team already arrive nested.

    Same role MDProject's legacy ``EventSerializer`` used to play; we just
    don't need a Django serializer because the aggregator side already
    produces the right shape.
    """
    return {**item, "event_id": item["id"]}


def build_available_events(match: Match) -> list[dict]:
    """Returns the list of event dicts the popup hydrates from."""
    if not match.end_date:
        return []

    cache_key = f"portal:events:match:{match.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    starts_after = (timezone.now() + OWNER_DEADLINE_BUFFER).isoformat()
    starts_before = match.end_date.isoformat()

    try:
        body = AggrigatorClient().list_events(
            starts_after=starts_after,
            starts_before=starts_before,
            page_size=200,
        )
    except AggrigatorError as exc:
        logger.warning(
            "aggregator unreachable for match=%s available_events: %s",
            match.id, exc,
        )
        return []

    items = [_shape_for_popup(it) for it in (body.get("items") or [])]
    cache.set(cache_key, items, timeout=CACHE_TTL)
    return items


@require_GET
@login_required(login_url="/auth/login/")
@player_in_match_required
def available_events_for_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    return JsonResponse({"items": build_available_events(match)})
