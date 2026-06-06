"""Test factories.

Tiny helpers that build the smallest valid graph for each domain object.
Each call writes one row to the test DB. Tests should compose these directly
rather than relying on pytest-style fixtures so the setup is visible at the
call site.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, patch

from django.utils import timezone

from core.event.models import (
    Event,
    League,
    Market,
    MarketCategory,
    MarketScope,
    Selection,
    Sport,
    Team,
)
from core.event.models.odds.selection import SettlementSource, SettlementStatus
from core.game.models import Game
from core.match.models import Match
from core.user.models import User


def make_user(suffix: str = "") -> User:
    """Create a user with deterministic username/email."""
    suffix = suffix or uuid.uuid4().hex[:8]
    return User.objects.create_user(
        username=f"u_{suffix}",
        email=f"u_{suffix}@test.local",
        password="testpassword",
    )


def make_sport(sport_id: str = "FOOTBALL") -> Sport:
    sport, _ = Sport.objects.get_or_create(id=sport_id, defaults={"name": sport_id.title()})
    return sport


def make_league(
    league_id: str = "NFL",
    sport_id: str = "FOOTBALL",
    *,
    active: bool = True,
) -> League:
    sport = make_sport(sport_id)
    league, _ = League.objects.update_or_create(
        id=league_id,
        defaults={"sport": sport, "name": league_id, "active": active, "refresh_cadence_minutes": 720},
    )
    return league


def make_team(league: League, team_id: str, *, name: str | None = None) -> Team:
    pk = f"{league.id}:{team_id}"
    name = name or team_id.replace("_", " ").title()
    team, _ = Team.objects.update_or_create(
        id=pk,
        defaults={
            "league": league,
            "team_id": team_id,
            "sport": league.sport,
            "name_long": name,
            "name_medium": name[:64],
            "name_short": name[:32],
            "stat_entity_id": "",
        },
    )
    return team


def make_event(
    league: League,
    *,
    event_id: str | None = None,
    home: Team | None = None,
    away: Team | None = None,
    status_type: str = "notstarted",
    is_live: bool = False,
    is_finalized: bool = False,
    completed: bool = False,
    home_score: int | None = None,
    away_score: int | None = None,
    winner_code: int | None = None,
    start_time=None,
) -> Event:
    if home is None:
        home = make_team(league, "HOME_TEAM_TEST")
    if away is None:
        away = make_team(league, "AWAY_TEAM_TEST")
    event_id = event_id or uuid.uuid4().hex[:20]
    if start_time is None:
        start_time = timezone.now() + timedelta(days=2)

    derived_winner_code = winner_code
    if derived_winner_code is None and home_score is not None and away_score is not None:
        derived_winner_code = (
            1 if home_score > away_score else 2 if away_score > home_score else 3
        )

    event = Event.objects.create(
        id=event_id,
        sport=league.sport,
        league=league,
        type="match",
        season_label="",
        start_time=start_time,
        status_type=status_type,
        status_display=status_type,
        is_live=is_live,
        is_finalized=is_finalized,
        completed=completed,
        home_team=home,
        away_team=away,
        home_score=home_score,
        away_score=away_score,
        winner_code=derived_winner_code,
        winner=(
            home.name_long if derived_winner_code == 1
            else away.name_long if derived_winner_code == 2
            else "Draw" if derived_winner_code == 3
            else None
        ),
        feed_locked=False,
    )
    return event


def make_market(
    event: Event,
    *,
    category: str = MarketCategory.MONEYLINE,
    market_type: str | None = None,
    scope: str = MarketScope.FULL_GAME,
    line: Decimal | float | int | None = None,
    side: str = "",
    market_id: str | None = None,
    is_live: bool = False,
    suspended: bool = False,
) -> Market:
    if market_type is None:
        market_type = f"{event.league_id}_TEST_{category}"
    market_id = market_id or f"{event.id}-{category.lower()}-{uuid.uuid4().hex[:6]}"
    return Market.objects.create(
        id=market_id,
        event=event,
        sport=event.sport,
        category=category,
        type=market_type[:64],
        scope=scope,
        line=Decimal(str(line)) if line is not None else None,
        side=side,
        provider="sportsgameodds",
        provider_market_id=market_id,
        is_live=is_live,
        suspended=suspended,
        last_updated=timezone.now(),
    )


def make_selection(
    market: Market,
    *,
    selection_type: str,
    selection_id: str | None = None,
    odds: Decimal | float | str = "2.0000",
    settlement_status: str = SettlementStatus.PENDING,
    settlement_source: str = "",
    label: str | None = None,
) -> Selection:
    sid = selection_id or f"{market.id}:{selection_type.lower()}"
    return Selection.objects.create(
        id=sid,
        market=market,
        type=selection_type,
        label=label or f"{market.type} {selection_type}",
        decimal_odds=Decimal(str(odds)),
        opening_decimal_odds=Decimal(str(odds)),
        movement=0,
        suspended=False,
        settlement_status=settlement_status,
        settlement_source=settlement_source,
    )


def make_two_way_market(
    event: Event,
    *,
    category: str = MarketCategory.MONEYLINE,
    line: float | None = None,
    home_status: str = SettlementStatus.PENDING,
    away_status: str = SettlementStatus.PENDING,
    types: tuple[str, str] = ("HOME", "AWAY"),
) -> tuple[Market, Selection, Selection]:
    """A market with home + away (or over + under) selections returned ready."""
    market = make_market(event, category=category, line=line)
    a = make_selection(market, selection_type=types[0], settlement_status=home_status)
    b = make_selection(market, selection_type=types[1], settlement_status=away_status)
    return market, a, b


@contextmanager
def mock_golden_seed(selection: Selection):
    """Patch the aggregator listing + chain mirror that
    ``Game.objects.get_golden_game`` calls during ``accept_match``, so the
    Golden Game seeds from a locally-created (event, market, selection)
    without any HTTP. Both names are imported inside the function body, so
    patching the source modules at call time is sufficient."""
    market = selection.market
    listing = {
        "items": [{
            "id": market.event_id,
            "markets": [{
                "category": market.category,
                "scope": market.scope,
                "selections": [{
                    "id": selection.id,
                    "type": selection.type,
                    "decimal_odds": str(selection.decimal_odds),
                }],
            }],
        }],
    }
    client = MagicMock()
    client.list_events.return_value = listing
    with patch(
        "core.event.providers.aggregator_client.AggrigatorClient",
        return_value=client,
    ), patch(
        "core.event.services.aggregator_chain.ensure_chain",
        return_value=selection,
    ):
        yield


def make_golden_seed_selection() -> Selection:
    """A local event + MONEYLINE market the Golden Game can seed against."""
    league = make_league("GOLDEN_SEED")
    event = make_event(
        league,
        home=make_team(league, "GOLDEN_HOME"),
        away=make_team(league, "GOLDEN_AWAY"),
    )
    _, home_sel, _ = make_two_way_market(event)
    return home_sel


def make_match(
    player_1: User,
    player_2: User,
    *,
    end_date=None,
    accept: bool = True,
    golden_selection: Optional[Selection] = None,
) -> Match:
    """Build a Match. If ``accept=True`` (default) all 11 game slots are seeded
    via ``MatchManager.accept_match`` so it matches what production looks like
    after both players join. The Golden Game seed (an aggregator call in
    production) is mocked against ``golden_selection`` — pass one to control
    which event/market the golden slot locks, otherwise a dedicated
    GOLDEN_SEED event is created.
    """
    if end_date is None:
        end_date = timezone.now() + timedelta(weeks=1)

    if accept:
        if golden_selection is None:
            golden_selection = make_golden_seed_selection()
        with mock_golden_seed(golden_selection):
            match = Match.objects.create_match(player_1=player_1, player_2=player_2)
        # Match.objects.create_match already calls accept_match for private matches.
        # Ensure end_date is what the test expects.
        match.end_date = end_date
        match.save(update_fields=["end_date"])
        return match

    # Build a created-only match (no Game rows).
    return Match.objects.create(
        player_1=player_1,
        player_2=player_2,
        match_state="created",
        match_type="private",
        end_date=end_date,
    )


def assign_event_to_slot(
    game: Game,
    event: Event,
    *,
    owner_selection: Optional[Selection] = None,
    player_2_selection: Optional[Selection] = None,
) -> Game:
    """Wire an event + optional picks onto a Game directly (skipping
    upload_pick's deadline checks). Useful for tests that want to set up
    state and then test scoring/settlement, not the picking workflow."""
    game.event = event
    game.save(update_fields=["event"])
    if owner_selection is not None:
        from core.game.models.bet import Bet
        Bet.objects.set_owner_outcome(game.bet, owner_selection)
    if player_2_selection is not None:
        from core.game.models.bet import Bet
        Bet.objects.set_player_2_outcome(game.bet, player_2_selection)
    return game


def settle_selection(
    selection: Selection,
    status: str,
    *,
    source: str = SettlementSource.PROVIDER,
) -> Selection:
    selection.settlement_status = status
    selection.settled_at = timezone.now()
    selection.settlement_source = source
    selection.save(update_fields=["settlement_status", "settled_at", "settlement_source"])
    return selection
