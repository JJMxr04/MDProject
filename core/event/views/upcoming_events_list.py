"""Upcoming-events grid, server-rendered.

Source-of-truth for events: aggregator's ``GET /v1/events`` (plan §2.4.2).
The aggregator now ships ``sport``, ``league``, ``home_team``, ``away_team``
nested in each event (plan v2 portal redesign), so the template reads the
same `{{ event.sport.name }}` / `{{ event.home_team.name }}` it always did.

Failure modes:
- Aggregator 5xx / timeout → serve cached snapshot if present (TTL extended
  to 5 min in that case), otherwise show an error empty-state.
- Aggregator 401 (key revoked) → log warning, render error state.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache, caches
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
    search_query = request.GET.get("search", "").strip()
    selected_sport = request.GET.get("sport", "").strip()
    start_date = parse_date(request.GET.get("start_date", "") or "")
    user_end_date = parse_date(request.GET.get("end_date", "") or "")
    # ``int(...)`` blows up the whole view if someone hands us
    # ``?page=foo``. Treat any unparseable value as page 1 instead.
    try:
        page = max(1, int(request.GET.get("page", "1") or "1"))
    except (TypeError, ValueError):
        page = 1

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


def _safe_cache_get(key):
    """``cache.get`` that swallows cache-backend blowups.

    We hit this on every render. Without the swallow, a transient
    Postgres outage against the django_cache table turns every portal
    request into a 500 — the page is perfectly renderable from a fresh
    aggregator call, but the cache layer crashes the view before we get
    there.
    """
    try:
        return cache.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache.get(%s) failed (non-fatal): %s", key, exc)
        return None


def _safe_cache_set(key, value, timeout) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache.set(%s) failed (non-fatal): %s", key, exc)


def _fetch_or_cached(
    cache_key: str, **params,
) -> tuple[dict | None, bool]:
    """Fetch from aggregator + cache; on failure, serve cached if any.

    Returns ``(body, served_stale)``. ``body`` is None only when both fresh
    fetch and cache miss. Catches a broad Exception around the aggregator
    call — we'd rather show an empty grid with the "aggregator unreachable"
    banner than 500 the whole portal on an unexpected upstream response
    shape.
    """
    cached = _safe_cache_get(cache_key)
    client = AggrigatorClient()
    try:
        body = client.list_events(page_size=PAGE_SIZE, **params)
        _safe_cache_set(cache_key, body, CACHE_TTL_OK)
        return body, False
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for upcoming-events: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("unexpected aggregator failure for upcoming-events: %s", exc)
    if cached is not None:
        _safe_cache_set(cache_key, cached, CACHE_TTL_STALE)
        return cached, True
    return None, False


_LOCAL_CACHE = caches["local"]


def _sports_dropdown() -> list[dict]:
    """Aggregator's /v1/sports list, tiered cache.

    L1: per-worker in-process LocMem (60s) — zero network, ~no cost
        on cache hit. Worker-local, so writes propagate via natural
        expiry, not invalidation.
    L2: Upstash Redis (300s) — shared across workers, cross-region
        round-trip cost.
    L3: aggregator HTTP — fetch on cold miss.
    """
    cached = _LOCAL_CACHE.get("sports:dropdown")
    if cached is not None:
        return cached
    cached = _safe_cache_get("portal:sports:dropdown")
    if cached is not None:
        _LOCAL_CACHE.set("sports:dropdown", cached, 60)
        return cached
    try:
        sports = AggrigatorClient().get_sports() or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("sports dropdown fetch failed (non-fatal): %s", exc)
        sports = []
    _safe_cache_set("portal:sports:dropdown", sports, 300)
    _LOCAL_CACHE.set("sports:dropdown", sports, 60)
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
