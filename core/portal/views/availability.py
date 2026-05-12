"""Portal page that shows everything the system can currently bet on:

- Sports + leagues (live from the aggregator's references endpoints).
- Bookmakers we ship per-book quotes for.
- Market types — distinct values of ``Market.type`` from the aggregator
  (e.g. MONEYLINE, SPREAD, OVER_UNDER_POINTS, BTTS, etc.). Live from
  ``/v1/market-types``.

Every section is queried from the aggregator at request time (cached
briefly) so adding a new sport / league / bookmaker / market type on
the aggregator side automatically flows through without a code change
here.
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render

from core.event.providers.aggregator_client import AggrigatorClient, AggrigatorError

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 min — sports/leagues/bookmakers/markets change rarely


@login_required(login_url="/auth/login/")
def availability_view(request):
    sports, leagues, bookmakers, market_types, agg_unreachable = _load_catalog()

    # Build a {sport_id: count} for the leagues display.
    leagues_by_sport: dict[str, list[dict]] = {}
    for lg in leagues:
        leagues_by_sport.setdefault(lg.get("sport_id") or "", []).append(lg)

    return render(
        request,
        "portal/availability/availability.html",
        {
            "sports": sports,
            "leagues_by_sport": leagues_by_sport,
            "bookmakers": bookmakers,
            "market_types": market_types,
            "aggregator_unreachable": agg_unreachable,
        },
    )


def _safe_cache_get(key, default=None):
    """``cache.get`` that swallows Redis-side blowups. Without it, a
    misconfigured REDIS_URL turns this page into a 500 instead of just
    silently missing the cache."""
    try:
        return cache.get(key, default)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache.get(%s) failed (non-fatal): %s", key, exc)
        return default


def _safe_cache_set(key, value, timeout) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache.set(%s) failed (non-fatal): %s", key, exc)


def _safe_sort(items, attr="name"):
    """Sort dicts by an attribute, tolerating non-dict entries so an
    unexpected payload shape doesn't 500 the page."""
    return sorted(
        items or [],
        key=lambda x: (x.get(attr) if isinstance(x, dict) else "" or "").lower(),
    )


def _cached_fallback() -> tuple[list, list, list, list, bool]:
    """Last-known-good cache values + unreachable=True. Used both when
    the aggregator throws and when the cache itself blows up."""
    return (
        _safe_cache_get("portal:availability:sports", []) or [],
        _safe_cache_get("portal:availability:leagues", []) or [],
        _safe_cache_get("portal:availability:bookmakers", []) or [],
        _safe_cache_get("portal:availability:markets", []) or [],
        True,
    )


def _load_catalog():
    """Returns ``(sports, leagues, bookmakers, market_types, unreachable_flag)``.

    Cached briefly. On aggregator OR cache failure returns
    last-known-good values if cached, else empty lists +
    ``unreachable=True`` so the page can show a banner instead of
    crashing."""
    sports = _safe_cache_get("portal:availability:sports")
    leagues = _safe_cache_get("portal:availability:leagues")
    bookmakers = _safe_cache_get("portal:availability:bookmakers")
    market_types = _safe_cache_get("portal:availability:markets")
    if (
        sports is not None and leagues is not None
        and bookmakers is not None and market_types is not None
    ):
        return sports, leagues, bookmakers, market_types, False

    client = AggrigatorClient()
    try:
        sports = _safe_sort(client.get_sports())
        leagues = _safe_sort(client.get_leagues())
        bookmakers = _safe_sort(client.get_bookmakers())
        market_types = sorted(client.get_market_types() or [])
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for availability page: %s", exc)
        return _cached_fallback()
    except Exception as exc:  # noqa: BLE001
        logger.exception("unexpected aggregator failure on availability page: %s", exc)
        return _cached_fallback()

    _safe_cache_set("portal:availability:sports", sports, CACHE_TTL)
    _safe_cache_set("portal:availability:leagues", leagues, CACHE_TTL)
    _safe_cache_set("portal:availability:bookmakers", bookmakers, CACHE_TTL)
    _safe_cache_set("portal:availability:markets", market_types, CACHE_TTL)
    return sports, leagues, bookmakers, market_types, False
