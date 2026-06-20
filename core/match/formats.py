"""Match format presets (plan Phase 5, D-5).

Replaces the old hardcodes (5 games / 1-week window in match.py). A format
fixes the match shape at creation time — the invite carries it, accepting
is consent, and there is no mid-match renegotiation (D-5 #4).

Window and game count are per-player: every preset adds one shared Golden
Game on top (the explicit tiebreaker, D-5 #1), so the minimum distinct
events a window must offer is ``games_per_player + 1``.
"""

from __future__ import annotations

from datetime import timedelta

MATCH_FORMATS = {
    "BLITZ": {"label": "Blitz", "days": 2, "games_per_player": 2},
    "CLASSIC": {"label": "Classic", "days": 4, "games_per_player": 3},
    "MARATHON": {"label": "Marathon", "days": 7, "games_per_player": 5},
}

# Existing matches predate formats and were all the 5-games/7-day shape —
# exactly MARATHON — so it doubles as the migration default.
DEFAULT_FORMAT = "MARATHON"

FORMAT_CHOICES = [(key, cfg["label"]) for key, cfg in MATCH_FORMATS.items()]


def normalize_format(value) -> str:
    """Coerce client/payload input to a valid format key.

    Unknown or missing values fall back to DEFAULT_FORMAT rather than
    raising — a stale invite payload should never block an accept.
    """
    key = (value or "").strip().upper() if isinstance(value, str) else ""
    return key if key in MATCH_FORMATS else DEFAULT_FORMAT


def format_label(fmt: str) -> str:
    return MATCH_FORMATS[normalize_format(fmt)]["label"]


def format_window(fmt: str) -> timedelta:
    return timedelta(days=MATCH_FORMATS[normalize_format(fmt)]["days"])


def games_per_player(fmt: str) -> int:
    return MATCH_FORMATS[normalize_format(fmt)]["games_per_player"]


def min_distinct_events(fmt: str) -> int:
    """Fixture-availability bar (D-5 #2): regular slots + the Golden Game."""
    return games_per_player(fmt) + 1
