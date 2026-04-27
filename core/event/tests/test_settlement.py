"""Computed-path settlement — no SGO calls.

These tests fabricate Event/Market/Selection rows directly and verify that
``settle_event`` produces the right ``settlement_status`` for each category.
The grader-from-fixtures path is exercised in the smoke runs; here we test the
COMPUTED fallback in isolation.
"""

from decimal import Decimal

from django.test import TestCase

from core.event.models.odds.selection import SettlementSource, SettlementStatus
from core.event.odds.settlement import settle_event
from core.match.tests.factories import (
    make_event,
    make_league,
    make_selection,
    make_two_way_market,
)


class MoneylineSettlementTests(TestCase):
    def test_home_wins_two_way(self):
        league = make_league("NBA", "BASKETBALL")
        event = make_event(
            league, status_type="finished", is_finalized=True, completed=True,
            home_score=100, away_score=92,
        )
        _, home, away = make_two_way_market(event)

        settle_event(event)

        home.refresh_from_db()
        away.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.WON)
        self.assertEqual(away.settlement_status, SettlementStatus.LOST)
        self.assertEqual(home.settlement_source, SettlementSource.COMPUTED)

    def test_away_wins_two_way(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=10, away_score=24,
        )
        _, home, away = make_two_way_market(event)

        settle_event(event)

        home.refresh_from_db()
        away.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.LOST)
        self.assertEqual(away.settlement_status, SettlementStatus.WON)

    def test_three_way_draw(self):
        league = make_league("MLS", "SOCCER")
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=1, away_score=1, winner_code=3,
        )
        from core.event.models import MarketCategory

        market, home, away = make_two_way_market(event, category=MarketCategory.MONEYLINE)
        draw = make_selection(market, selection_type="DRAW")

        settle_event(event)

        home.refresh_from_db()
        away.refresh_from_db()
        draw.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.LOST)
        self.assertEqual(away.settlement_status, SettlementStatus.LOST)
        self.assertEqual(draw.settlement_status, SettlementStatus.WON)


class TotalSettlementTests(TestCase):
    def test_over_wins_when_total_above_line(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=27, away_score=24,  # total 51
        )
        from core.event.models import MarketCategory
        _, over, under = make_two_way_market(
            event, category=MarketCategory.TOTAL, line=44.5, types=("OVER", "UNDER"),
        )

        settle_event(event)

        over.refresh_from_db(); under.refresh_from_db()
        self.assertEqual(over.settlement_status, SettlementStatus.WON)
        self.assertEqual(under.settlement_status, SettlementStatus.LOST)

    def test_integer_line_pushes(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=24, away_score=20,  # total 44
        )
        from core.event.models import MarketCategory
        _, over, under = make_two_way_market(
            event, category=MarketCategory.TOTAL, line=44, types=("OVER", "UNDER"),
        )

        settle_event(event)

        over.refresh_from_db(); under.refresh_from_db()
        self.assertEqual(over.settlement_status, SettlementStatus.PUSH)
        self.assertEqual(under.settlement_status, SettlementStatus.PUSH)


class SpreadSettlementTests(TestCase):
    def test_home_covers(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=27, away_score=20,  # margin +7 (home perspective)
        )
        from core.event.models import MarketCategory
        # Home -3.5 → adjusted = 7 + (-3.5) = +3.5 → home WON
        _, home, away = make_two_way_market(event, category=MarketCategory.SPREAD, line=-3.5)

        settle_event(event)

        home.refresh_from_db(); away.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.WON)
        self.assertEqual(away.settlement_status, SettlementStatus.LOST)

    def test_integer_line_push_spread(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=24, away_score=21,  # margin +3
        )
        from core.event.models import MarketCategory
        # Home -3 → adjusted = +3 + (-3) = 0 → PUSH
        _, home, away = make_two_way_market(event, category=MarketCategory.SPREAD, line=-3)

        settle_event(event)

        home.refresh_from_db(); away.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.PUSH)
        self.assertEqual(away.settlement_status, SettlementStatus.PUSH)


class SourcePriorityTests(TestCase):
    def test_manual_source_never_overwritten_by_computed(self):
        league = make_league()
        event = make_event(
            league, status_type="finished", is_finalized=True,
            home_score=30, away_score=10,
        )
        _, home, away = make_two_way_market(event)
        # Operator manually overrode home → LOST. Computed wants WON. MANUAL stays.
        home.settlement_status = SettlementStatus.LOST
        home.settlement_source = SettlementSource.MANUAL
        home.save(update_fields=["settlement_status", "settlement_source"])

        settle_event(event)

        home.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.LOST)
        self.assertEqual(home.settlement_source, SettlementSource.MANUAL)
        # The away side is still PENDING when settle_event ran (priority skipped
        # the MANUAL row but the away row was COMPUTED-able).
        away.refresh_from_db()
        self.assertEqual(away.settlement_status, SettlementStatus.LOST)


class UnfinishedEventTests(TestCase):
    def test_settle_event_noops_on_inprogress(self):
        league = make_league()
        event = make_event(league, status_type="inprogress", is_live=True)
        _, home, away = make_two_way_market(event)

        result = settle_event(event)

        self.assertEqual(result, 0)
        home.refresh_from_db(); away.refresh_from_db()
        self.assertEqual(home.settlement_status, SettlementStatus.PENDING)
        self.assertEqual(away.settlement_status, SettlementStatus.PENDING)
