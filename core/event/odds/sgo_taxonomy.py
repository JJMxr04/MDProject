"""SportsGameOdds oddID taxonomy.

An SGO oddID decomposes as ``"{statID}-{statEntityID}-{periodID}-{betTypeID}-{sideID}"``
(see ``api-switch/sports_game/odds-system-plan.md``). This module provides the
splitter plus the three small lookup tables that map SGO components onto our
existing ``MarketCategory`` / ``MarketScope`` / ``SelectionType`` enums.

Pure functions only — no Django imports. Safe to use from tests or scripts.

Adding a new league or sport: add rows to the maps below, no code path changes.
Adding a new betType: one line. Adding a new period: one line plus a possible
``MarketScope`` enum value (model migration).
"""

from __future__ import annotations

from typing import NamedTuple

# ---- bet types --------------------------------------------------------------

#: Maps SGO ``betTypeID`` to our ``MarketCategory`` value.
#:
#: Values in our ``MarketCategory`` enum: MONEYLINE, SPREAD, TOTAL, PROPS_GAME,
#: PROPS_TEAM. Player props (PROPS_PLAYER) are deliberately not enabled.
BET_TYPE_TO_CATEGORY: dict[str, str] = {
    "ml":     "MONEYLINE",       # 2-way home/away
    "ml3way": "MONEYLINE",       # 3-way home/draw/away (soccer; some hockey reg-only)
    "sp":     "SPREAD",          # spread / handicap / puck line / run line
    "ou":     "TOTAL",           # over/under (may promote to PROPS_TEAM, see normalize)
    "yn":     "PROPS_GAME",      # yes/no — BTTS, OT-yes-no, etc.
    "eo":     "PROPS_GAME",      # even/odd
}


# ---- periods ----------------------------------------------------------------

#: Maps SGO ``periodID`` strings to our ``MarketScope`` enum values.
#:
#: SGO emits sport-specific period sets. We unify them under our scope axis.
#: Sports we cover: BASEBALL (1i..9i), BASKETBALL (1q..4q), FOOTBALL (1q..4q),
#: HOCKEY (1p..3p, so), SOCCER (1h, 2h).
PERIOD_TO_SCOPE: dict[str, str] = {
    "game":  "FULL_GAME",
    "reg":   "FULL_GAME",        # regulation only — distinguished by type, not scope
    "1h":    "H1",  "2h": "H2",
    "1q":    "Q1",  "2q": "Q2",  "3q": "Q3",  "4q": "Q4",
    "1p":    "P1",  "2p": "P2",  "3p": "P3",
    "ot":    "OVERTIME",
    "so":    "SHOOTOUT",
    # Baseball innings
    "1i": "INNING_1",  "2i": "INNING_2",  "3i": "INNING_3",
    "4i": "INNING_4",  "5i": "INNING_5",  "6i": "INNING_6",
    "7i": "INNING_7",  "8i": "INNING_8",  "9i": "INNING_9",
    # Baseball aggregate windows (when SGO ships them)
    "1st5":  "INNINGS_1_5",
    "1st3":  "INNINGS_1_3",
    # Basketball minute windows
    "5min":  "MINUTES_5",
    "10min": "MINUTES_10",
}


# ---- sides ------------------------------------------------------------------

#: Maps SGO ``sideID`` to our ``SelectionType`` enum value.
SIDE_TO_SELECTION: dict[str, str] = {
    "home":  "HOME",
    "away":  "AWAY",
    "draw":  "DRAW",
    "over":  "OVER",
    "under": "UNDER",
    "yes":   "YES",
    "no":    "NO",
    "even":  "EVEN",
    "odd":   "ODD",
}


# ---- type overrides ---------------------------------------------------------

#: Override the auto-generated ``Market.type`` string for specific
#: ``(statID, statEntityID, periodID, betTypeID, sideID)`` tuples.
#:
#: Use sparingly — only when the auto-generated name is ambiguous or ugly.
#: The mapping value is a function of (league_id) -> type string so the same
#: rule applies to e.g. BTTS across MLS / EPL / UCL.
#:
#: For most markets the auto-generated ``f"{LEAGUE}_{STAT}_{BETTYPE}"`` is fine.
TYPE_OVERRIDES: dict[tuple[str, str, str, str, str], "TypeOverrideFn"] = {
    # Soccer BTTS — both teams to score
    ("goals", "all", "game", "yn", "yes"): lambda lg: f"{lg}_BTTS",
    ("goals", "all", "game", "yn", "no"):  lambda lg: f"{lg}_BTTS",
    # Hockey puck line — naming convention
    ("goals", "home", "game", "sp", "home"): lambda lg: f"{lg}_PUCK_LINE" if lg == "NHL" else None,
    ("goals", "away", "game", "sp", "away"): lambda lg: f"{lg}_PUCK_LINE" if lg == "NHL" else None,
    # MLB run line
    ("runs", "home", "game", "sp", "home"): lambda lg: f"{lg}_RUN_LINE" if lg == "MLB" else None,
    ("runs", "away", "game", "sp", "away"): lambda lg: f"{lg}_RUN_LINE" if lg == "MLB" else None,
}


# ---- splitter ---------------------------------------------------------------


class OddIDParts(NamedTuple):
    statID: str
    statEntityID: str
    periodID: str
    betTypeID: str
    sideID: str


def parse_odd_id(odd_id: str) -> OddIDParts:
    """Split an SGO oddID into its 5 components.

    ``"points-home-game-ml-home"`` -> ``OddIDParts("points", "home", "game", "ml", "home")``.

    Raises ``ValueError`` if the input doesn't have exactly 5 dash-separated
    parts. Callers should treat malformed oddIDs as skip-worthy (log + continue),
    not crash.

    Note on player props: SGO encodes the playerID in the ``statEntityID`` slot
    (e.g., ``"TRAVIS_KELCE_1_NFL"``). Those are single tokens — playerIDs use
    underscores, never dashes — so the simple 5-tuple split works.
    """
    parts = odd_id.split("-")
    if len(parts) != 5:
        raise ValueError(f"Malformed oddID (expected 5 dash-separated parts): {odd_id!r}")
    return OddIDParts(*parts)


# ---- type generation --------------------------------------------------------


def market_type_for(parts: OddIDParts, league_id: str) -> str:
    """Return the canonical ``Market.type`` string for an oddID + league.

    Default: ``f"{LEAGUE}_{STAT.upper()}_{BETTYPE.upper()}"`` (e.g., ``"NFL_POINTS_ML"``).
    Overridden for specific tuples in ``TYPE_OVERRIDES``.
    """
    key = (parts.statID, parts.statEntityID, parts.periodID, parts.betTypeID, parts.sideID)
    fn = TYPE_OVERRIDES.get(key)
    if fn is not None:
        override = fn(league_id)
        if override is not None:
            return override
    return f"{league_id}_{parts.statID.upper()}_{parts.betTypeID.upper()}"


# Type alias used above — kept at module bottom for forward-reference clarity.
TypeOverrideFn = "callable[[str], str | None]"
