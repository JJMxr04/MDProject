"""Transforms raw SofaScore `get-all-odds` payloads into rows of
`Market` / `Selection` / `OddsQuote`. Idempotent upserts on deterministic
string market ids + stable SofaScore selection ids.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.event.models import Event, Market, Selection
from core.event.models.odds.quote import OddsQuote
from core.event.odds.converters import fractional_to_decimal
from core.event.odds.settlement import apply_provider_flag
from core.event.odds.taxonomy import SCOPE_MAP, SOFASCORE_MARKET_MAP, MarketSpec

logger = logging.getLogger(__name__)

# log once per (sport_id, market_id, period) we don't recognise
_unknown_markets_logged: set[tuple[int, int, str]] = set()


def build_market_id(
    event_id: int,
    kind_slug: str,
    scope: str,
    line: float | None,
    side: str | None = None,
) -> str:
    scope_slug = {
        "FULL_GAME": "ft",
        "H1": "h1",
        "H2": "h2",
        "Q1": "q1",
        "Q2": "q2",
        "Q3": "q3",
        "Q4": "q4",
        "OVERTIME": "ot",
        "PERIOD_N": "pn",
        "P1": "p1",
        "P2": "p2",
        "P3": "p3",
        "SHOOTOUT": "so",
    }.get(scope, scope.lower())
    parts = [f"evt-{event_id}", kind_slug, scope_slug]
    if line is not None:
        parts.append(str(line).replace(".", "_"))
    if side:
        parts.append(side.lower())
    return "-".join(parts)


def classify_choice(
    spec: MarketSpec, raw_name: str, *, home_team: str, away_team: str
) -> tuple[str, str]:
    """Return `(SelectionType, label)`. Falls back to ``("CUSTOM", raw_name)``
    so unknown markets still render cleanly even if they aren't filterable."""

    n = (raw_name or "").strip()

    if spec.category == "MONEYLINE" and spec.type == "SOCCER_MATCH_WINNER":
        if n == "1":
            return "HOME", home_team
        if n == "X":
            return "DRAW", "Draw"
        if n == "2":
            return "AWAY", away_team

    if spec.category == "TOTAL":
        if n.startswith("Over"):
            return "OVER", n
        if n.startswith("Under"):
            return "UNDER", n

    if spec.type == "SOCCER_BTTS":
        return ("YES", "Yes") if n == "Yes" else ("NO", "No")

    if spec.type == "SOCCER_DOUBLE_CHANCE":
        if n in ("1X", "X2", "12"):
            return n, n

    if spec.type == "SOCCER_DRAW_NO_BET":
        if n == "1":
            return "HOME", home_team
        if n == "2":
            return "AWAY", away_team

    if spec.type == "SOCCER_ASIAN_HANDICAP":
        if home_team and home_team in n:
            return "HOME", n
        if away_team and away_team in n:
            return "AWAY", n

    if spec.type == "SOCCER_FIRST_SCORER":
        if n == "No goal":
            return "NO_GOAL", "No goal"
        if home_team and home_team in n:
            return "HOME", n
        if away_team and away_team in n:
            return "AWAY", n

    if spec.type in ("SOCCER_CORNERS_TOTAL", "SOCCER_CARDS_TOTAL"):
        if n.startswith("Over"):
            return "OVER", n
        if n.startswith("Under"):
            return "UNDER", n

    # --- Hockey ---
    if spec.type in ("NHL_MATCH_WINNER_INC_OT", "NHL_PERIOD_WINNER"):
        if n == "1":
            return "HOME", home_team
        if n == "X":
            return "DRAW", "Draw"
        if n == "2":
            return "AWAY", away_team

    if spec.type == "NHL_MATCH_WINNER_REG":
        if n == "1":
            return "HOME", home_team
        if n == "X":
            return "DRAW", "Draw (regulation)"
        if n == "2":
            return "AWAY", away_team

    if spec.type == "NHL_PUCK_LINE":
        # label like "(-1.5) Toronto Maple Leafs" or "(+1.5) Boston Bruins"
        if home_team and home_team in n:
            return "HOME", n
        if away_team and away_team in n:
            return "AWAY", n

    if spec.type in ("NHL_MATCH_GOALS", "NHL_PERIOD_TOTAL"):
        if n.startswith("Over"):
            return "OVER", n
        if n.startswith("Under"):
            return "UNDER", n

    if spec.type == "NHL_BTTS":
        return ("YES", "Yes") if n.lower().startswith("yes") else ("NO", "No")

    if spec.type == "NHL_FIRST_GOAL_SCORER_TEAM":
        if n == "No goal":
            return "NO_GOAL", "No goal"
        if home_team and home_team in n:
            return "HOME", n
        if away_team and away_team in n:
            return "AWAY", n

    return "CUSTOM", n


def _log_unknown(sport_id: int, provider_market_id: int, period: str) -> None:
    key = (sport_id, provider_market_id, period)
    if key in _unknown_markets_logged:
        return
    _unknown_markets_logged.add(key)
    logger.info(
        "Skipping unknown SofaScore market: sport=%s market_id=%s period=%r",
        sport_id,
        provider_market_id,
        period,
    )


@transaction.atomic
def ingest_odds(event: Event, payload: dict) -> int:
    """Upsert markets and selections from a SofaScore odds payload.

    Returns the number of markets ingested.
    """
    if not payload:
        return 0

    home_name = event.home_team.name if event.home_team else ""
    away_name = event.away_team.name if event.away_team else ""
    now = timezone.now()
    markets_ingested = 0

    for raw_market in payload.get("markets") or []:
        period = raw_market.get("marketPeriod") or "Full-time"
        provider_market_id = raw_market.get("marketId")
        if provider_market_id is None:
            continue

        spec = SOFASCORE_MARKET_MAP.get((event.sport_id, int(provider_market_id), period))
        if spec is None:
            _log_unknown(event.sport_id, int(provider_market_id), period)
            continue

        scope = SCOPE_MAP.get(period, "FULL_GAME")
        line_str = raw_market.get("choiceGroup")
        try:
            line = Decimal(line_str) if line_str not in (None, "") else None
        except (ValueError, TypeError):
            line = None

        market_id = build_market_id(event.id, spec.kind_slug, scope, line, side=None)
        market, _ = Market.objects.update_or_create(
            id=market_id,
            defaults=dict(
                event=event,
                sport_id=event.sport_id,
                category=spec.category,
                type=spec.type,
                scope=scope,
                line=line,
                provider="sofascore",
                provider_market_id=int(provider_market_id),
                provider_choice_group=line_str or "",
                is_live=bool(raw_market.get("isLive")),
                suspended=bool(raw_market.get("suspended", False)),
                last_updated=now,
            ),
        )

        for raw_choice in raw_market.get("choices") or []:
            source_id = raw_choice.get("sourceId")
            if source_id is None:
                continue

            sel_type, label = classify_choice(
                spec,
                raw_choice.get("name", ""),
                home_team=home_name,
                away_team=away_name,
            )
            decimal_odds = fractional_to_decimal(raw_choice.get("fractionalValue", ""))
            opening = fractional_to_decimal(
                raw_choice.get("initialFractionalValue")
                or raw_choice.get("fractionalValue", "")
            )
            movement = int(raw_choice.get("change") or 0)

            sel, created = Selection.objects.update_or_create(
                id=int(source_id),
                defaults=dict(
                    market=market,
                    type=sel_type,
                    label=label,
                    decimal_odds=decimal_odds,
                    opening_decimal_odds=opening,
                    movement=movement,
                    suspended=bool(raw_choice.get("suspended", False)),
                ),
            )

            # Movement row only on actual price change
            if created or sel.decimal_odds != decimal_odds:
                OddsQuote.objects.get_or_create(
                    selection=sel,
                    captured_at=now,
                    defaults={"decimal_odds": decimal_odds},
                )

            # SofaScore ships `winning: true|false` on finished-game payloads.
            # Copy it through — provider is authoritative over our computed
            # settlement.
            if apply_provider_flag(sel, raw_choice.get("winning"), now=now):
                sel.save(
                    update_fields=["settlement_status", "settled_at", "settlement_source"]
                )

        markets_ingested += 1

    return markets_ingested
