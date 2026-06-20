"""Turn league-prefixed ``Market.type`` strings into readable market labels
and a per-league coverage matrix for the availability page.

``Market.type`` is built by the aggregator as ``f"{LEAGUE_ID}_{STAT}_{BETTYPE}"``
(uppercase), where ``LEAGUE_ID`` is exactly the league's ``id``. A few types are
overridden (``*_BTTS``, ``NHL_PUCK_LINE``, ``MLB_RUN_LINE``). Because some league
ids are prefixes of others (``VNL`` vs ``VNL_WOMEN``), a type is attributed to the
league with the LONGEST matching id prefix.
"""
from __future__ import annotations

# Stats that represent the game score (so their ML/OU/SP are "core" game markets,
# not player props).
_SCORE_STATS = {"POINTS", "GOALS", "RUNS"}

# Canonical (prefix-stripped) types with bespoke names.
_OVERRIDE_LABELS = {
    "BTTS": "Both Teams to Score",
    "RUN_LINE": "Run Line",
    "PUCK_LINE": "Puck Line",
}

# Score-stat bet-type -> core market label.
_CORE_BETTYPE = {
    "ML": "Moneyline",
    "ML3WAY": "Match Result (3-Way)",
    "SP": "Spread",
    "OU": "Total",
}

# Bet-type -> human suffix for prop markets.
_PROP_SUFFIX = {
    "OU": "O/U",
    "YN": "Yes/No",
    "EO": "Even/Odd",
    "ML": "ML",
    "ML3WAY": "3-Way",
    "SP": "Spread",
}

# Display order for the well-known core columns; everything else sorts after, alpha.
_CORE_ORDER = [
    "Moneyline",
    "Match Result (3-Way)",
    "Spread",
    "Total",
    "Both Teams to Score",
    "Run Line",
    "Puck Line",
]


def split_market_type(market_type, league_ids):
    """Return ``(league_id, canonical)`` for ``market_type`` using the longest
    case-insensitive ``league_id + "_"`` prefix match, else ``(None, None)``.
    ``canonical`` is the remainder, uppercased."""
    if not market_type:
        return None, None
    mt = market_type.upper()
    best = None
    for lid in league_ids:
        if not lid:
            continue
        if mt.startswith(lid.upper() + "_") and (best is None or len(lid) > len(best)):
            best = lid
    if best is None:
        return None, None
    return best, market_type[len(best) + 1:].upper()


def humanize_market_type(canonical):
    """Map a prefix-stripped canonical market (e.g. ``GOALS_ML3WAY``) to a
    readable label."""
    if not canonical:
        return "Market"
    if canonical in _OVERRIDE_LABELS:
        return _OVERRIDE_LABELS[canonical]
    parts = canonical.split("_")
    bettype = parts[-1]
    stat_tokens = parts[:-1]
    stat = "_".join(stat_tokens)
    if stat in _SCORE_STATS and bettype in _CORE_BETTYPE:
        return _CORE_BETTYPE[bettype]
    stat_title = " ".join(t.title() for t in stat_tokens)
    suffix = _PROP_SUFFIX.get(bettype, bettype.title())
    return f"{stat_title} {suffix}".strip() if stat_title else suffix


def column_sort_key(label):
    """Sort core columns first (in ``_CORE_ORDER``), then the rest alphabetically."""
    if label in _CORE_ORDER:
        return (0, _CORE_ORDER.index(label))
    return (1, label.lower())


def build_sport_matrix(leagues, market_types):
    """Assemble one sport's grid.

    ``leagues``: list of ``{"id", "name"}`` dicts. ``market_types``: that sport's
    league-prefixed type strings. Returns ``{"columns": [...], "rows": [...]}``
    where each row is ``{"league": <name or id>, "cells": [bool, ...]}`` aligned to
    ``columns``. ``columns`` is empty when no type matched any league."""
    league_ids = [lg.get("id") for lg in leagues if lg.get("id")]
    labels_by_league: dict[str, set] = {}
    all_labels: set = set()
    for mt in market_types:
        lid, canonical = split_market_type(mt, league_ids)
        if lid is None:
            continue
        label = humanize_market_type(canonical)
        labels_by_league.setdefault(lid, set()).add(label)
        all_labels.add(label)

    columns = sorted(all_labels, key=column_sort_key)
    rows = []
    for lg in leagues:
        lid = lg.get("id")
        present = labels_by_league.get(lid, set())
        rows.append({
            "league": lg.get("name") or lid or "",
            "cells": [col in present for col in columns],
        })
    return {"columns": columns, "rows": rows}
