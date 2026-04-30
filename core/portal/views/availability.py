"""Portal page that shows everything the system can currently bet on:

- Sports + leagues (live from the aggregator's references endpoints).
- Bookmakers we ship per-book quotes for.
- Market categories + per-sport "special prop" support, marked WIP for the
  combinations we don't yet COMPUTED-settle.

The aggregator is queried at request time (cached briefly) so adding a new
sport/league/bookmaker on the aggregator side automatically flows through
without a code change here.

The "WIP" matrix at the bottom is a small static map maintained by hand —
flip a cell from WIP to ✓ when COMPUTED settlement lands for that sport's
special prop type.
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render

from core.event.providers.aggregator_client import AggrigatorClient, AggrigatorError

logger = logging.getLogger(__name__)

CACHE_TTL = 300  # 5 min — sports/leagues/bookmakers change rarely

# Per-sport special-prop COMPUTED settlement coverage. Mirrors
# ``aggrigator/aggrigator/ingest/settlement_computed.py`` —
# keep in sync when COMPUTED settlement is added for a new sport.
#
# ML/SP/TOTAL on FULL_GAME are sport-agnostic (just need home_score +
# away_score + winner_code), so they're "✓" for every sport. The matrix
# below tracks the SPECIAL props that need per-sport logic.
PROP_COVERAGE = [
    # (sport label, BTTS, double-chance, draw-no-bet, team_total)
    {"sport": "Football",   "btts": "wip", "dc": "n/a", "dnb": "n/a", "ttg": "wip"},
    {"sport": "Basketball", "btts": "n/a", "dc": "n/a", "dnb": "n/a", "ttg": "wip"},
    {"sport": "Baseball",   "btts": "wip", "dc": "n/a", "dnb": "n/a", "ttg": "wip"},
    {"sport": "Hockey",     "btts": "ok",  "dc": "n/a", "dnb": "n/a", "ttg": "ok"},
    {"sport": "Soccer",     "btts": "ok",  "dc": "ok",  "dnb": "ok",  "ttg": "ok"},
    {"sport": "Tennis",     "btts": "n/a", "dc": "n/a", "dnb": "n/a", "ttg": "n/a"},
    {"sport": "MMA",        "btts": "n/a", "dc": "n/a", "dnb": "n/a", "ttg": "n/a"},
]

# Universal market categories — these settle from event scores alone and
# work for every sport. Tracked separately from the per-sport prop matrix.
UNIVERSAL_MARKETS = [
    {"category": "MONEYLINE",  "scope": "FULL_GAME",  "label": "Moneyline (full game)",   "status": "ok"},
    {"category": "SPREAD",     "scope": "FULL_GAME",  "label": "Point spread (full game)","status": "ok"},
    {"category": "TOTAL",      "scope": "FULL_GAME",  "label": "Over / Under (full game)","status": "ok"},
    {"category": "MONEYLINE",  "scope": "Q1/Q2/Q3/Q4","label": "Per-quarter moneyline",   "status": "wip"},
    {"category": "SPREAD",     "scope": "1H/2H",      "label": "Per-half spread",         "status": "wip"},
]


@login_required(login_url="/auth/login/")
def availability_view(request):
    sports, leagues, bookmakers, agg_unreachable = _load_catalog()

    # Build a {sport_id: count} for the leagues display.
    leagues_by_sport: dict[str, list[dict]] = {}
    for lg in leagues:
        leagues_by_sport.setdefault(lg.get("sport_id") or "", []).append(lg)

    # Stitch the static prop-coverage matrix to the live sport list when
    # the labels overlap so the table only shows sports the aggregator
    # actually returns. Anything in PROP_COVERAGE without a matching
    # sport in ``sports`` is dropped (avoids advertising sports we
    # don't ingest).
    sport_labels_lower = {(s.get("name") or "").lower() for s in sports}
    visible_props = [
        row for row in PROP_COVERAGE
        if row["sport"].lower() in sport_labels_lower
    ]

    return render(
        request,
        "portal/availability/availability.html",
        {
            "sports": sports,
            "leagues_by_sport": leagues_by_sport,
            "bookmakers": bookmakers,
            "universal_markets": UNIVERSAL_MARKETS,
            "prop_coverage": visible_props,
            "aggregator_unreachable": agg_unreachable,
        },
    )


def _load_catalog():
    """Returns ``(sports, leagues, bookmakers, unreachable_flag)``.

    Cached briefly. On aggregator failure returns last-known-good values
    if cached, else empty lists + ``unreachable=True`` so the page can
    show a banner instead of crashing."""
    sports = cache.get("portal:availability:sports")
    leagues = cache.get("portal:availability:leagues")
    bookmakers = cache.get("portal:availability:bookmakers")
    if sports is not None and leagues is not None and bookmakers is not None:
        return sports, leagues, bookmakers, False

    client = AggrigatorClient()
    try:
        sports = sorted(client.get_sports() or [], key=lambda s: (s.get("name") or "").lower())
        leagues = sorted(client.get_leagues() or [], key=lambda l: (l.get("name") or "").lower())
        bookmakers = sorted(client.get_bookmakers() or [], key=lambda b: (b.get("name") or "").lower())
    except AggrigatorError as exc:
        logger.warning("aggregator unreachable for availability page: %s", exc)
        # Last-known-good cache fallback (extended TTL) — we'd rather show
        # a slightly stale list than a blank page.
        return (
            cache.get("portal:availability:sports", []),
            cache.get("portal:availability:leagues", []),
            cache.get("portal:availability:bookmakers", []),
            True,
        )

    cache.set("portal:availability:sports", sports, timeout=CACHE_TTL)
    cache.set("portal:availability:leagues", leagues, timeout=CACHE_TTL)
    cache.set("portal:availability:bookmakers", bookmakers, timeout=CACHE_TTL)
    return sports, leagues, bookmakers, False
