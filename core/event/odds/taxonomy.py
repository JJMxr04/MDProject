"""Single source of truth that maps SofaScore market payloads to our
`MarketCategory` / `MarketScope` / `type` tuple. When SofaScore ships a
market we don't recognise the ingest skips it and logs once — extending the
system means appending rows to these two dicts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketSpec:
    category: str  # MarketCategory value
    type: str  # e.g. "SOCCER_BTTS"
    kind_slug: str  # short slug used in the deterministic market_id


# Key: (sport_id, provider_market_id, market_period)
SOFASCORE_MARKET_MAP: dict[tuple[int, int, str], MarketSpec] = {
    # Soccer (1)
    (1, 1, "Full-time"): MarketSpec("MONEYLINE", "SOCCER_MATCH_WINNER", "ml"),
    (1, 1, "1st half"): MarketSpec("MONEYLINE", "SOCCER_MATCH_WINNER", "ml"),
    (1, 2, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_DOUBLE_CHANCE", "dc"),
    (1, 3, "1st half"): MarketSpec("MONEYLINE", "SOCCER_MATCH_WINNER", "ml"),
    (1, 4, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_DRAW_NO_BET", "dnb"),
    (1, 5, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_BTTS", "btts"),
    (1, 6, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_FIRST_SCORER", "first"),
    (1, 9, "Full-time"): MarketSpec("TOTAL", "SOCCER_MATCH_GOALS", "total"),
    # Asian handicap is disabled until the normalizer can parse the line from
    # the choice name (SofaScore puts it inside the label e.g. "(2.25) Burnley"
    # rather than in `choiceGroup`, so `market.line` lands as None and the
    # settlement engine correctly punts). Re-enable once normalize.py handles
    # that extraction for SPREAD markets.
    # (1, 17, "Full-time"): MarketSpec("SPREAD", "SOCCER_ASIAN_HANDICAP", "spread"),
    (1, 20, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_CARDS_TOTAL", "cards"),
    (1, 21, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_CORNERS_TOTAL", "corners"),
    # Basketball (2) and American football (63): populate once we've inspected
    # a real payload for each. Unknown markets are skipped at ingest time.
    # Ice hockey (4) - SofaScore uses marketPeriod="Match" for full-game
    # hockey markets (not "Full-time" like soccer). Period markets for hockey
    # are "1st period" / "2nd period" / "3rd period" — but have not been
    # observed live yet, so they stay as placeholders.
    (4, 1, "Match"): MarketSpec("MONEYLINE", "NHL_MATCH_WINNER_INC_OT", "ml"),
    (4, 60, "Regulation"): MarketSpec("MONEYLINE", "NHL_MATCH_WINNER_REG", "mlreg"),
    (4, 17, "Match"): MarketSpec("SPREAD", "NHL_PUCK_LINE", "spread"),
    (4, 9, "Match"): MarketSpec("TOTAL", "NHL_MATCH_GOALS", "total"),
    (4, 1, "1st period"): MarketSpec("MONEYLINE", "NHL_PERIOD_WINNER", "ml"),
    (4, 1, "2nd period"): MarketSpec("MONEYLINE", "NHL_PERIOD_WINNER", "ml"),
    (4, 1, "3rd period"): MarketSpec("MONEYLINE", "NHL_PERIOD_WINNER", "ml"),
    (4, 9, "1st period"): MarketSpec("TOTAL", "NHL_PERIOD_TOTAL", "total"),
    (4, 9, "2nd period"): MarketSpec("TOTAL", "NHL_PERIOD_TOTAL", "total"),
    (4, 9, "3rd period"): MarketSpec("TOTAL", "NHL_PERIOD_TOTAL", "total"),
    (4, 5, "Match"): MarketSpec("PROPS_GAME", "NHL_BTTS", "btts"),
    (4, 6, "Match"): MarketSpec("PROPS_GAME", "NHL_FIRST_GOAL_SCORER_TEAM", "firstteam"),
}


SCOPE_MAP: dict[str, str] = {
    "Full-time": "FULL_GAME",
    "1st half": "H1",
    "2nd half": "H2",
    "1st quarter": "Q1",
    "2nd quarter": "Q2",
    "3rd quarter": "Q3",
    "4th quarter": "Q4",
    "Overtime": "OVERTIME",
    # Hockey
    "Match": "FULL_GAME",
    "1st period": "P1",
    "2nd period": "P2",
    "3rd period": "P3",
    "Regulation": "FULL_GAME",
    "Shootout": "SHOOTOUT",
}


# Subject axis ("who is this market about?") derived from MarketCategory.
# Keeps the REST layer's ?scope_subject=player|team|game sugar consistent.
SUBJECT_SCOPE_BY_CATEGORY: dict[str, str] = {
    "MONEYLINE": "game",
    "SPREAD": "game",
    "TOTAL": "game",
    "PROPS_GAME": "game",
    "PROPS_TEAM": "team",
}


def subject_scope(category: str) -> str:
    return SUBJECT_SCOPE_BY_CATEGORY.get(category, "game")
