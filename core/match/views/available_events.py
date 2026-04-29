"""``available_events_for_match`` — server-side helper for the pick popup.

Returns the catalog of events a user can pick from for one match's window.
Replaces the local-DB filter that used to live in ``myMatchDetail.py:46-54``;
post-cutover the catalog comes from the aggregator (plan §2.4.2).

Two callers:
- ``my_match_detail_view`` calls ``build_available_events(match)`` to populate
  the JSON island at template line 162.
- A standalone JSON endpoint (URL name ``portal-available-events-for-match``)
  is exposed for HTMX / fetch-based callers; the popup currently uses the
  JSON island, so this endpoint is here for future use without breaking the
  current page.

Both paths share the same caching layer.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
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


def build_available_events(match: Match) -> list[dict]:
    """Returns the list of event dicts the popup hydrates from."""
    if not match.end_date:
        return []

    cache_key = f"portal:events:match:{match.id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    if not getattr(settings, "USE_AGGRIGATOR", False):
        return _legacy_local_db_list(match)

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
        return cached if cached is not None else []

    items = body.get("items") or []
    cache.set(cache_key, items, timeout=CACHE_TTL)
    return items


@require_GET
@login_required(login_url="/auth/login/")
@player_in_match_required
def available_events_for_match(request, match_id):
    match = get_object_or_404(Match, id=match_id)
    return JsonResponse({"items": build_available_events(match)})


# ---- legacy fallback ------------------------------------------------------


def _legacy_local_db_list(match: Match) -> list[dict]:
    """``USE_AGGRIGATOR=False`` rollback path — original logic from
    myMatchDetail.py:46-54."""
    from core.event.models import Event
    from core.event.serializers.event import EventSerializer

    cutoff = timezone.now() + OWNER_DEADLINE_BUFFER
    events = Event.objects.filter(
        start_time__gte=cutoff,
        start_time__lte=match.end_date,
        completed=False,
    ).select_related("sport", "home_team", "away_team").order_by("start_time")
    return EventSerializer(events, many=True).data
