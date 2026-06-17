"""Normalized card data for the portal VS-card / event-matchup components.

One ``fixture`` shape feeds three sources — the local ``Event`` model (duels),
the aggregator event dict (upcoming events), and (indirectly) matches — so the
duels, matches and upcoming-events pages render the same league / time / score /
winner cluster from a single set of templates.
"""
from __future__ import annotations

from django.utils.dateparse import parse_datetime

from core.event.providers.aggregator_client import absolutize_logo_url


def _status(*, is_live: bool, is_final: bool) -> str:
    if is_final:
        return "final"
    if is_live:
        return "live"
    return "upcoming"


def team_side(*, name=None, logo_url=None, score=None) -> dict:
    return {"name": name or "TBD", "logo_url": logo_url or "", "score": score}


def fixture_from_event(event) -> dict | None:
    """Fixture from a local ``core.event.models.Event`` row (duels/matches)."""
    if event is None:
        return None
    home, away = event.home_team, event.away_team
    is_final = bool(
        event.is_finalized or event.completed or event.status_type == "finished"
    )
    status = _status(is_live=bool(event.is_live), is_final=is_final)

    def _logo(team):
        # Team.logo_url is now a string serve-URL (or None), not an ImageFieldFile.
        return team.logo_url if (team and team.logo_url) else None

    return {
        "league_name": event.league.name if event.league_id else "",
        "start_time": event.start_time,
        "status": status,
        "home": team_side(
            name=home.name if home else None, logo_url=_logo(home), score=event.home_score
        ),
        "away": team_side(
            name=away.name if away else None, logo_url=_logo(away), score=event.away_score
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
    status = _status(is_live=bool(ev.get("is_live")), is_final=is_final)

    start = ev.get("start_time")
    if isinstance(start, str):
        start = parse_datetime(start) or start

    return {
        "league_name": (ev.get("league") or {}).get("name") or "",
        "start_time": start,
        "status": status,
        "home": team_side(
            name=home.get("name"),
            logo_url=absolutize_logo_url(home.get("logo_url")),
            score=ev.get("home_score"),
        ),
        "away": team_side(
            name=away.get("name"),
            logo_url=absolutize_logo_url(away.get("logo_url")),
            score=ev.get("away_score"),
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
