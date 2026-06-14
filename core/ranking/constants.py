"""Tunable weights for the progression system (phase 8, D-8).

Everything that decides "how much" lives here so re-tuning never needs a
migration (``XpEvent.source`` is an enum, so the ledger replays cleanly). Three
tracks, deliberately different in character:

- **Level (XP):** never resets; permanent cosmetic track.
- **Season points:** reset each season; orders the season rank.
- **Global points:** never reset; the career sum of the same point awards;
  orders the global rank.

Elo is computed and stored but does NOT order leaderboards v1 — it's the skill
signal for provisional placement and future features.
"""

from __future__ import annotations

# --- format weighting (D-5 #3): longer commitment out-earns spam -----------
# Mirrors the XP completion ratios (Blitz 50 : Classic 80 : Marathon 120).
FORMAT_WEIGHT = {
    "BLITZ": 1.0,
    "CLASSIC": 1.6,
    "MARATHON": 2.4,
}
DEFAULT_FORMAT_WEIGHT = 1.0


def format_weight(fmt: str) -> float:
    return FORMAT_WEIGHT.get((fmt or "").upper(), DEFAULT_FORMAT_WEIGHT)


# --- XP (level track) -------------------------------------------------------
# Base completion XP is the Blitz number; format weight scales it, so a
# Marathon completion ≈ 2.4× a Blitz one.
XP_MATCH_COMPLETED_BASE = 50
XP_MATCH_WIN_BONUS_FRACTION = 0.5  # +50% of the (weighted) completion award
XP_GOLDEN_PICK_HIT = 25
XP_POTD_PICK_MADE = 10
XP_POTD_PICK_WON = 25
XP_POTD_STREAK = {7: 50, 30: 250, 100: 1000}
XP_DUEL_WON = 20
XP_SEASON_TOP3 = 200


# --- points (both ranks share one award table) ------------------------------
# Season points and global points are credited together at one chokepoint.
PTS_MATCH_WIN_BASE = 100
PTS_MATCH_DRAW_BASE = 50
PTS_MATCH_PARTICIPATION = 10   # both players, every completed match
PTS_GOLDEN_HIT = 25
PTS_POTD_WIN = 40
PTS_POTD_PARTICIPATION = 5
PTS_SEASON_FINISH_TOP3 = 150   # global_points only (career bridge)


# --- Elo (recorded, not ranked on v1) ---------------------------------------
ELO_START = 1200
ELO_K_BASE = 32
ELO_PROVISIONAL_MATCHES = 5     # K doubled for a player's first N ranked matches
ELO_PROVISIONAL_MULTIPLIER = 2.0


# --- divisions / season lifecycle ------------------------------------------
# Don't fragment a tester-sized population: one division until there are enough
# ranked players, then split into bands. Next-season division follows final
# standing (that's promotion/relegation in its simplest form).
DIVISION_SPLIT_THRESHOLD = 30   # ranked players before divisions split
DIVISION_SIZE = 20              # players per division once split
SEASON_ELIGIBILITY_FLOOR = 3    # min ranked games to appear on the leaderboard
MISSING_NEXT_SEASON_WARN_DAYS = 7  # warn if no DRAFT within N days of close
SEASON_FINISH_TOP_N = 3         # top-N per division earn badges + finish bonus


# --- level curve ------------------------------------------------------------
# Cumulative XP to *reach* level n. Level 1 = 0 XP; early levels fast, later
# slow (n^1.5). One Classic win (~120 XP) lands a new player at level 2.
LEVEL_CURVE_COEFF = 100
LEVEL_CURVE_EXP = 1.5


def xp_to_reach_level(level: int) -> int:
    if level <= 1:
        return 0
    return round(LEVEL_CURVE_COEFF * (level - 1) ** LEVEL_CURVE_EXP)


def level_for_xp(xp: int) -> int:
    """Highest level whose cumulative threshold is within ``xp``."""
    level = 1
    while xp_to_reach_level(level + 1) <= xp:
        level += 1
    return level
