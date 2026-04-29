"""Upcoming-events grid, server-rendered.

After the aggregator cutover (plan §2.4.2) this view proxies to
``GET /v1/events`` instead of reading from MDProject's local DB. Failure
modes:

- Aggregator 5xx / timeout → serve cached snapshot if present (TTL extended
  to 5 min in that case), otherwise show an error empty-state.
- Aggregator 401 (key revoked) → log to Sentry as warning, error state.
- ``USE_AGGRIGATOR=False`` (rollback path): fall back to legacy local-DB
  query unchanged, so flipping the env flag back is a clean revert.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    AggrigatorError,
)

logger = logging.getLogger(__name__)


PAGE_SIZE = 21
CACHE_TTL_OK = 60       # seconds — fresh aggregator data
CACHE_TTL_STALE = 300   # seconds — extended on aggregator failure


def _as_aware(d, end_of_day=False):
    if not d:
        return None
    t = time.max if end_of_day else time.min
    return timezone.make_aware(datetime.combine(d, t))


@login_required(login_url="/auth/login/")
def upcoming_events_list(request):
    if not getattr(settings, "USE_AGGRIGATOR", False):
        return _legacy_local_db_path(request)

    search_query = request.GET.get("search", "").strip()
    selected_sport = request.GET.get("sport", "").strip()
    start_date = parse_date(request.GET.get("start_date", "") or "")
    user_end_date = parse_date(request.GET.get("end_date", "") or "")
    page = int(request.GET.get("page", "1") or "1")

    max_end_date = timezone.now().date() + timedelta(days=90)
    end_date = min(user_end_date, max_end_date) if user_end_date else max_end_date
    floor = _as_aware(start_date) if start_date else timezone.now()
    ceiling = _as_aware(end_date, end_of_day=True)

    cache_key = (
        f"portal:events:upcoming:{selected_sport}:{floor.isoformat()}"
        f":{ceiling.isoformat()}:{page}:{search_query}"
    )

    body, served_stale = _fetch_or_cached(
        cache_key,
        sport=selected_sport or None,
        starts_after=floor.isoformat(),
        starts_before=ceiling.isoformat(),
        page=page,
    )

    if body is None:
        # Catastrophic — no fresh data, no cached snapshot.
        return render(
            request,
            "portal/event/upcoming-events-list.html",
            {
                "page_obj": _empty_page(),
                "sports": _sports_dropdown(),
                "search_query": search_query,
                "selected_sport": selected_sport,
                "start_date": request.GET.get("start_date", ""),
                "end_date": request.GET.get("end_date", ""),
                "aggregator_error": True,
            },
            status=503,
        )

    items = body.get("items") or []
    if search_query:
        ql = search_query.lower()
        def _matches(ev: dict) -> bool:
            hay = " ".join(filter(None, [
                (ev.get("home_team") or {}).get("name_long"),
                (ev.get("away_team") or {}).get("name_long"),
                ev.get("season_label"),
            ])).lower()
            return ql in hay
        items = [ev for ev in items if _matches(ev)]

    page_obj = _AggregatorPage(
        items=items,
        page=body.get("page", page),
        page_size=body.get("page_size", PAGE_SIZE),
        total=body.get("total", len(items)),
        pages=body.get("pages", 1),
    )

    return render(
        request,
        "portal/event/upcoming-events-list.html",
        {
            "page_obj": page_obj,
            "sports": _sports_dropdown(),
            "search_query": search_query,
            "selected_sport": selected_sport,
            "start_date": request.GET.get("start_date", ""),
            "end_date": request.GET.get("end_date", ""),
            "served_stale": served_stale,
        },
    )


# ---- helpers ---------------------------------------------------------------


def _fetch_or_cached(
    cache_key: str, **params,
) -> tuple[dict | None, bool]:
    """Fetch from aggregator + cache; on failure, serve cached if any.

    Returns ``(body, served_stale)``. ``body`` is None only when both fresh
    fetch and cache miss.
    """
    cached = cache.get(cache_key)
    client = AggrigatorClient()
    try:
        body = client.list_events(page_size=PAGE_SIZE, **params)
        cache.set(cache_key, body, timeout=CACHE_TTL_OK)
        return body, False
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for upcoming-events: %s", exc)
        if cached is not None:
            cache.set(cache_key, cached, timeout=CACHE_TTL_STALE)
            return cached, True
        return None, False


def _sports_dropdown() -> list[dict]:
    """Aggregator's /v1/sports list, cached aggressively. Cheap; rarely changes."""
    cached = cache.get("portal:sports:dropdown")
    if cached is not None:
        return cached
    try:
        sports = AggrigatorClient().get_sports()
    except AggrigatorError:
        sports = []
    cache.set("portal:sports:dropdown", sports, timeout=300)
    return sports


def _empty_page() -> "_AggregatorPage":
    return _AggregatorPage(items=[], page=1, page_size=PAGE_SIZE, total=0, pages=1)


class _AggregatorPage:
    """Adapter that mimics Django's Paginator page so the existing template
    works unchanged. Implements the same surface ``{{ page_obj }}`` uses:
    iterable, ``object_list``, ``paginator`` access, ``has_previous`` etc.
    """

    def __init__(
        self, *, items: list[dict], page: int, page_size: int, total: int, pages: int,
    ):
        self.object_list = items
        self.number = page
        self._page_size = page_size
        self._pages = pages
        self.paginator = _AggregatorPaginator(total=total, num_pages=pages)

    def __iter__(self):
        return iter(self.object_list)

    def __len__(self):
        return len(self.object_list)

    def has_previous(self) -> bool:
        return self.number > 1

    def has_next(self) -> bool:
        return self.number < self._pages

    def previous_page_number(self) -> int:
        return max(1, self.number - 1)

    def next_page_number(self) -> int:
        return min(self._pages, self.number + 1)


class _AggregatorPaginator:
    def __init__(self, *, total: int, num_pages: int):
        self.count = total
        self.num_pages = num_pages

    def page_range(self):
        return range(1, self.num_pages + 1)


# ---- legacy fallback (rollback path) --------------------------------------


def _legacy_local_db_path(request):
    """Pre-cutover behavior — keep working when ``USE_AGGRIGATOR=False``.
    This is the original view logic verbatim (the working tree before
    Part 2.4 landed)."""
    from django.db.models import Exists, OuterRef, Q
    from core.event.models import Event, Sport
    from core.event.models.odds.market import Market

    search_query = request.GET.get("search", "").strip()
    selected_sport = request.GET.get("sport", "").strip()
    start_date = parse_date(request.GET.get("start_date", "") or "")
    user_end_date = parse_date(request.GET.get("end_date", "") or "")

    max_end_date = timezone.now().date() + timedelta(days=90)
    end_date = min(user_end_date, max_end_date) if user_end_date else max_end_date
    default_floor = timezone.now()

    has_markets = Market.objects.filter(event=OuterRef("pk"))
    events = (
        Event.objects.filter(completed=False)
        .annotate(has_markets=Exists(has_markets))
        .filter(has_markets=True)
        .select_related("home_team", "away_team", "sport")
        .order_by("start_time")
    )
    if search_query:
        events = events.filter(
            Q(season_label__icontains=search_query)
            | Q(home_team__name_long__icontains=search_query)
            | Q(away_team__name_long__icontains=search_query)
        )
    if selected_sport:
        events = events.filter(sport_id=selected_sport)

    floor = _as_aware(start_date) if start_date else default_floor
    events = events.filter(
        Q(status_type="inprogress") | Q(start_time__gte=floor),
        start_time__lte=_as_aware(end_date, end_of_day=True),
    )

    paginator = Paginator(events, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    sports = (
        Sport.objects.filter(events__completed=False, events__markets__isnull=False)
        .distinct()
        .order_by("name")
    )
    return render(
        request,
        "portal/event/upcoming-events-list.html",
        {
            "page_obj": page_obj,
            "sports": sports,
            "search_query": search_query,
            "selected_sport": selected_sport,
            "start_date": request.GET.get("start_date", ""),
            "end_date": request.GET.get("end_date", ""),
        },
    )
