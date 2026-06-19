"""Normalized card data for the portal VS-card / event-matchup components.

One ``fixture`` shape feeds three sources — the local ``Event`` model (duels),
the aggregator event dict (upcoming events), and (indirectly) matches — so the
duels, matches and upcoming-events pages render the same league / time / score /
winner cluster from a single set of templates.
"""
from __future__ import annotations

from django.utils.dateparse import parse_datetime

from core.event.providers.aggregator_client import proxy_logo_url

# Provider status_type values that map to a non-playing state. The aggregator
# emits "postponed"/"canceled" (one L); local Events use the same strings.
_POSTPONED_STATUSES = {"postponed", "delayed"}
_CANCELED_STATUSES = {"canceled", "cancelled"}


def _status(*, is_live: bool, is_final: bool, status_type: str | None = None) -> str:
    if is_final:
        return "final"
    st = status_type.lower() if isinstance(status_type, str) else None
    if st in _POSTPONED_STATUSES:
        return "postponed"
    if st in _CANCELED_STATUSES:
        return "canceled"
    if is_live:
        return "live"
    return "upcoming"


def _hex_to_rgb(c):
    """'#RRGGBB' or '#RRGGBBAA' -> (r, g, b), or None if unparseable."""
    if not c or not isinstance(c, str):
        return None
    c = c.lstrip("#")
    if len(c) < 6:
        return None
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


# Euclidean RGB distance below this -> "too similar to tell apart".
_TINT_CLASH_THRESHOLD = 60


def resolve_matchup_tints(home_color, away_color):
    """Return (home_tint, away_tint) for the matchup side gradients.

    Each is the team's own color, or None meaning "use the CSS default"
    (blue for home, red for away). If both teams have colors that are
    near-identical, BOTH return None so the two sides stay visually
    distinct on the default blue/red.
    """
    h, a = _hex_to_rgb(home_color), _hex_to_rgb(away_color)
    if h and a:
        dist = sum((x - y) ** 2 for x, y in zip(h, a)) ** 0.5
        if dist < _TINT_CLASH_THRESHOLD:
            return None, None
    return (home_color if h else None), (away_color if a else None)


def team_side(*, name=None, logo_url=None, score=None, tint=None) -> dict:
    return {"name": name or "TBD", "logo_url": logo_url or "", "score": score, "tint": tint}


def fixture_from_event(event) -> dict | None:
    """Fixture from a local ``core.event.models.Event`` row (duels/matches)."""
    if event is None:
        return None
    home, away = event.home_team, event.away_team
    is_final = bool(
        event.is_finalized or event.completed or event.status_type == "finished"
    )
    status = _status(
        is_live=bool(event.is_live), is_final=is_final,
        status_type=event.status_type,
    )

    def _logo(team):
        # Team.logo_url is now a string serve-URL (or None), not an ImageFieldFile.
        return team.logo_url if (team and team.logo_url) else None

    home_tint, away_tint = resolve_matchup_tints(
        getattr(home, "primary_color", None),
        getattr(away, "primary_color", None),
    )

    return {
        "league_name": event.league.name if event.league_id else "",
        "start_time": event.start_time,
        "status": status,
        "home": team_side(
            name=home.name if home else None, logo_url=_logo(home),
            score=event.home_score, tint=home_tint,
        ),
        "away": team_side(
            name=away.name if away else None, logo_url=_logo(away),
            score=event.away_score, tint=away_tint,
        ),
        "winner_label": event.winner if status == "final" else None,
    }


def fixture_from_dict(ev) -> dict | None:
    """Fixture from an aggregator event dict (upcoming-events page)."""
    if not ev:
        return None
    home = ev.get("home_team") or {}
    away = ev.get("away_team") or {}
    is_final = bool(
        ev.get("is_finalized") or ev.get("completed") or ev.get("status_type") == "finished"
    )
    status = _status(
        is_live=bool(ev.get("is_live")), is_final=is_final,
        status_type=ev.get("status_type"),
    )

    start = ev.get("start_time")
    if isinstance(start, str):
        start = parse_datetime(start) or start

    home_tint, away_tint = resolve_matchup_tints(
        home.get("primary_color"), away.get("primary_color")
    )

    return {
        "league_name": (ev.get("league") or {}).get("name") or "",
        "start_time": start,
        "status": status,
        "home": team_side(
            name=home.get("name"),
            logo_url=proxy_logo_url(home.get("logo_url")),
            score=ev.get("home_score"),
            tint=home_tint,
        ),
        "away": team_side(
            name=away.get("name"),
            logo_url=proxy_logo_url(away.get("logo_url")),
            score=ev.get("away_score"),
            tint=away_tint,
        ),
        "winner_label": ev.get("winner") if status == "final" else None,
    }


def match_outcome(match, user) -> dict:
    """Who-won pill for a multi-game Match, from ``user``'s perspective."""
    if match.match_state != "completed":
        return {"state": "pending", "label": "In progress"}
    wid = match.winner_id
    if wid is None:
        return {"state": "draw", "label": "Draw"}
    if wid == user.id:
        return {"state": "won", "label": "You won"}
    return {"state": "lost", "label": "Lost"}
