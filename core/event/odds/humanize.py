"""Plain-English rendering for picks.

Stored data: ``selection.label`` is "Moneyline" or "Spread" — fine for
debugging, opaque to a user. ``humanize_selection(sel)`` turns it into
"Detroit Red Wings to win @ 1.44" so a friend reading someone's match
detail page actually understands what was picked.

Two entry points:
- ``humanize_selection(selection)`` — for Django Selection model rows.
- ``humanize_payload(event, market, selection)`` — for raw aggregator
  dicts (used on the upcoming-event detail page which renders directly
  from the aggregator response).

Both share the same per-category renderers and JS mirror
(``humanizeSelection`` in ``my_match_detail.html``).
"""

from __future__ import annotations

from typing import Optional


def humanize_selection(selection) -> str:
    """Render a Selection as a plain-English phrase.

    Caller is responsible for select_related("market", "market__event",
    "market__event__home_team", "market__event__away_team",
    "market__subject_team") so we don't issue extra queries per render.

    Falls back to ``selection.label`` if we don't have enough context
    to render — never crashes.
    """
    if selection is None:
        return ""

    market = getattr(selection, "market", None)
    if market is None:
        return selection.label or selection.type or ""

    event = getattr(market, "event", None)
    home = (event.home_team.name_long if event and event.home_team else None) or "Home"
    away = (event.away_team.name_long if event and event.away_team else None) or "Away"

    cat = market.category
    sel_type = selection.type
    line = market.line

    if cat == "MONEYLINE":
        return _moneyline(home, away, sel_type, market.scope)
    if cat == "SPREAD":
        return _spread(home, away, sel_type, line, market.scope)
    if cat == "TOTAL":
        return _total(sel_type, line, market.scope)
    if cat == "PROPS_TEAM":
        subject = getattr(market, "subject_team", None)
        team_name = subject.name_long if subject else (home if market.side == "HOME" else away)
        return _props_team(team_name, market.type, sel_type, line)
    if cat == "PROPS_GAME":
        return _props_game(home, away, market.type, sel_type)

    # Unknown category — best-effort fallback.
    return selection.label or sel_type or "Pick"


def humanize_payload(event: dict | None, market: dict | None, selection: dict | None) -> str:
    """Same rendering as ``humanize_selection`` but for the raw aggregator
    dict shape (used by templates that consume the JSON response directly,
    not Django models)."""
    if not selection:
        return ""
    if not market:
        return selection.get("label") or selection.get("type") or ""

    home_team = (event or {}).get("home_team") or {}
    away_team = (event or {}).get("away_team") or {}
    home = home_team.get("name") or home_team.get("name_long") or "Home"
    away = away_team.get("name") or away_team.get("name_long") or "Away"

    cat = market.get("category")
    sel_type = selection.get("type")
    line = market.get("line")
    scope = market.get("scope")

    if cat == "MONEYLINE":
        return _moneyline(home, away, sel_type, scope)
    if cat == "SPREAD":
        return _spread(home, away, sel_type, line, scope)
    if cat == "TOTAL":
        return _total(sel_type, line, scope)
    if cat == "PROPS_TEAM":
        subj = market.get("subject_team") or {}
        team_name = (
            subj.get("name") or subj.get("name_long")
            or (home if market.get("side") == "HOME" else away)
        )
        return _props_team(team_name, market.get("type"), sel_type, line)
    if cat == "PROPS_GAME":
        return _props_game(home, away, market.get("type"), sel_type)
    return selection.get("label") or sel_type or "Pick"


# ---- Per-category renderers ------------------------------------------------


def _moneyline(home: str, away: str, sel_type: str, scope: Optional[str]) -> str:
    scope_hint = _scope_hint(scope)
    if sel_type == "HOME":
        return f"{home} to win{scope_hint}"
    if sel_type == "AWAY":
        return f"{away} to win{scope_hint}"
    if sel_type == "DRAW":
        return f"Draw{scope_hint}"
    return f"{sel_type}{scope_hint}"


def _spread(home: str, away: str, sel_type: str, line, scope: Optional[str]) -> str:
    """Spread is stored home-perspective: ``line=-3.5`` means home is favored
    by 3.5, away gets +3.5. Surface the sign that matches the bettor's side.
    Accepts ``line`` as Decimal, float, str, or None (aggregator wire format
    serializes Decimals as strings)."""
    scope_hint = _scope_hint(scope)
    line_num = _to_float(line)
    if sel_type == "HOME":
        suffix = f" {_format_line(line_num)}" if line_num is not None else ""
        return f"{home}{suffix}{scope_hint}"
    if sel_type == "AWAY":
        # Flip the sign for the away side so the user sees their own line.
        suffix = f" {_format_line(-line_num)}" if line_num is not None else ""
        return f"{away}{suffix}{scope_hint}"
    suffix = f" {_format_line(line_num)}" if line_num is not None else ""
    return f"{sel_type}{suffix}{scope_hint}"


def _to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _total(sel_type: str, line, scope: Optional[str]) -> str:
    scope_hint = _scope_hint(scope)
    if line is None:
        return f"{sel_type.title()}{scope_hint}"
    return f"{sel_type.title()} {line}{scope_hint}"


def _props_team(team: str, mkt_type: str, sel_type: str, line) -> str:
    """e.g. 'Detroit Red Wings team total Over 2.5'."""
    topic = _topic_from_market_type(mkt_type)
    line_part = f" {line}" if line is not None else ""
    return f"{team} {topic} {sel_type.title()}{line_part}"


def _props_game(home: str, away: str, mkt_type: str, sel_type: str) -> str:
    """Soccer/NHL game props that aren't simple over/under."""
    if mkt_type in ("SOCCER_BTTS", "NHL_BTTS"):
        return "Both teams to score: Yes" if sel_type == "YES" else "Both teams to score: No"
    if mkt_type == "SOCCER_DOUBLE_CHANCE":
        return {
            "1X": f"{home} or Draw",
            "X2": f"{away} or Draw",
            "12": f"{home} or {away} (no draw)",
        }.get(sel_type, sel_type)
    if mkt_type == "SOCCER_DRAW_NO_BET":
        if sel_type == "HOME":
            return f"{home} to win (draw refunds)"
        if sel_type == "AWAY":
            return f"{away} to win (draw refunds)"
    # Unknown prop: best-effort fall back to type + side.
    topic = _topic_from_market_type(mkt_type)
    return f"{topic}: {sel_type.replace('_', ' ').title()}"


# ---- Helpers ---------------------------------------------------------------


def _topic_from_market_type(mkt_type: Optional[str]) -> str:
    """``NHL_TEAM_TOTAL_GOALS`` → ``team total goals``. Sport prefix is
    stripped because the team name already conveys it."""
    if not mkt_type:
        return "prop"
    parts = mkt_type.lower().split("_")
    # Drop a leading sport prefix if present (NFL/NHL/NBA/NCAAF/MLB/SOCCER/...).
    if parts and parts[0] in {
        "nfl", "nhl", "nba", "ncaaf", "ncaab", "mlb", "soccer",
        "tennis", "mma", "ufc", "uefa", "champions",
    }:
        parts = parts[1:]
    return " ".join(parts) if parts else "prop"


def _format_line(line) -> str:
    """``-3.5`` → ``"-3.5"``, ``3.5`` → ``"+3.5"``. Strips trailing zeros."""
    try:
        n = float(line)
    except (TypeError, ValueError):
        return str(line)
    sign = "+" if n > 0 else ""
    # Trim "3.0" → "3"; keep "3.5" as-is.
    text = f"{n:g}"
    return f"{sign}{text}"


def _scope_hint(scope: Optional[str]) -> str:
    """SHows scope when it isn't FULL_GAME so users know it's a sub-period
    bet (e.g. '(1st half)'). Returns empty string for full-game markets."""
    if not scope or scope == "FULL_GAME":
        return ""
    pretty = {
        "1H": "1st half", "2H": "2nd half",
        "Q1": "1st quarter", "Q2": "2nd quarter",
        "Q3": "3rd quarter", "Q4": "4th quarter",
        "1P": "1st period", "2P": "2nd period", "3P": "3rd period",
    }.get(scope, scope.replace("_", " ").title())
    return f" ({pretty})"
