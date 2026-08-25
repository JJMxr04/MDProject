"""Tests for ``ensure_chain_from_aggregator`` — the get-or-create chain
builder used by the pick-submit views.

Stubs the aggregator client; we only care about the local DB writes.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from core.event.models import Event, League, Market, Selection, Sport, Team
from core.event.services.aggregator_chain import ChainBuildError, ensure_chain


def _markets_response(*, event_id: str, selection_id: str) -> dict:
    """Shape ``get_event(event_id, include_markets=True)`` returns — a flat
    ``EventDetailOut``: event fields at top level + ``markets`` array, with
    the canonical ``id`` primary key on every entity (post plan v2)."""
    return {
        "id": event_id,
        "sport_id": "FOOTBALL",
        "league_id": "NFL",
        "type": "match",
        "season_label": "2024-W15",
        "start_time": "2026-01-01T18:00:00Z",
        "status_type": "notstarted",
        "status_display": "Scheduled",
        "is_live": False, "is_finalized": False, "completed": False,
        "feed_locked": False,
        "home_team": {
            "team_id": "DAL", "league_id": "NFL",
            "name_long": "Dallas Cowboys",
            "name_medium": "Cowboys", "name_short": "DAL",
            "primary_color": "#003594", "stat_entity_id": "home",
        },
        "away_team": {
            "team_id": "PHI", "league_id": "NFL",
            "name_long": "Philadelphia Eagles",
            "name_medium": "Eagles", "name_short": "PHI",
            "primary_color": "#004C54", "stat_entity_id": "away",
        },
        "home_score": None, "away_score": None,
        "winner_code": None,
        "markets": [
            {
                "id": f"{event_id}-ml-ft",
                "category": "MONEYLINE", "type": "NFL_POINTS_ML",
                "scope": "FULL_GAME", "line": None, "side": "",
                "subject_team_id": None,
                "is_live": False, "suspended": False,
                "selections": [
                    {
                        "id": selection_id,
                        "type": "HOME", "label": "Dallas Cowboys",
                        "decimal_odds": "1.6700",
                        "opening_decimal_odds": "1.7500",
                        "movement": -1,
                        "settlement_status": "PENDING",
                        "settlement_source": "",
                        "settled_at": None,
                    },
                ],
            },
        ],
    }


def _two_way_markets_response(*, event_id: str, home_id: str, away_id: str) -> dict:
    """Like ``_markets_response`` but the moneyline market carries BOTH priced
    sides — the shape duels rely on (``opposite_selection`` resolves the second
    side from the local mirror)."""
    body = _markets_response(event_id=event_id, selection_id=home_id)
    body["markets"][0]["selections"].append({
        "id": away_id,
        "type": "AWAY", "label": "Philadelphia Eagles",
        "decimal_odds": "2.2000",
        "opening_decimal_odds": "2.1000",
        "movement": 1,
        "settlement_status": "PENDING",
        "settlement_source": "",
        "settled_at": None,
    })
    return body


@override_settings(USE_AGGRIGATOR=True)
class EnsureChainTests(TestCase):
    def setUp(self):
        self.event_id = "evt-test-123"
        self.selection_id = f"{self.event_id}-ml-ft:home-home"
        self.payload = _markets_response(
            event_id=self.event_id, selection_id=self.selection_id,
        )

    def _patch_client(self, body):
        return patch(
            "core.event.services.aggregator_chain.AggrigatorClient",
            return_value=type("C", (), {
                "get_event": lambda _self, _id, include_markets=True: body,
            })(),
        )

    def test_first_call_creates_full_chain(self):
        with self._patch_client(self.payload):
            sel = ensure_chain(self.event_id, self.selection_id)
        # Chain is in place
        self.assertIsNotNone(Sport.objects.filter(id="FOOTBALL").first())
        self.assertIsNotNone(League.objects.filter(id="NFL").first())
        self.assertIsNotNone(Team.objects.filter(id="NFL:DAL").first())
        self.assertIsNotNone(Team.objects.filter(id="NFL:PHI").first())
        self.assertIsNotNone(Event.objects.filter(id=self.event_id).first())
        self.assertIsNotNone(Market.objects.filter(id=f"{self.event_id}-ml-ft").first())
        self.assertEqual(sel.id, self.selection_id)
        self.assertEqual(sel.decimal_odds, Decimal("1.6700"))
        self.assertEqual(sel.market.type, "NFL_POINTS_ML")
        self.assertEqual(sel.market.event_id, self.event_id)

    def test_second_call_is_idempotent(self):
        """Re-running ``ensure_chain`` for the same (event, selection) creates
        no new rows — get_or_create on PKs is concurrency-safe."""
        with self._patch_client(self.payload):
            ensure_chain(self.event_id, self.selection_id)
            ensure_chain(self.event_id, self.selection_id)
        self.assertEqual(Sport.objects.count(), 1)
        self.assertEqual(League.objects.count(), 1)
        self.assertEqual(Team.objects.count(), 2)
        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Market.objects.count(), 1)
        self.assertEqual(Selection.objects.count(), 1)

    def test_refreshes_stale_event_lifecycle(self):
        """An existing local mirror with a stale terminal status must be
        refreshed from the aggregator response — a stale ``finished`` row
        freezes the game card (``is_settled``) even though the event hasn't
        kicked off (seen after sim reseeds that reuse event ids)."""
        with self._patch_client(self.payload):
            ensure_chain(self.event_id, self.selection_id)
        Event.objects.filter(id=self.event_id).update(
            status_type="finished", is_finalized=True, completed=True,
        )
        with self._patch_client(self.payload):
            ensure_chain(self.event_id, self.selection_id)
        ev = Event.objects.get(id=self.event_id)
        self.assertEqual(ev.status_type, "notstarted")
        self.assertFalse(ev.is_finalized)
        self.assertFalse(ev.completed)

    def test_aggregator_unreachable_raises(self):
        """If the aggregator returns nothing, surface a clear error so the
        view can return 400 instead of persisting a half-built chain."""
        with patch(
            "core.event.services.aggregator_chain.AggrigatorClient",
            return_value=type("C", (), {"get_event": lambda *_, **__: None})(),
        ):
            with self.assertRaises(ChainBuildError):
                ensure_chain(self.event_id, self.selection_id)
        # No partial state left behind.
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Selection.objects.count(), 0)

    def test_default_mirrors_only_chosen_selection(self):
        """Without ``mirror_full_market``, only the picked side lands locally —
        the golden-game path needs just the one row."""
        home_id = self.selection_id
        away_id = f"{self.event_id}-ml-ft:away-away"
        body = _two_way_markets_response(
            event_id=self.event_id, home_id=home_id, away_id=away_id,
        )
        with self._patch_client(body):
            ensure_chain(self.event_id, home_id)
        self.assertEqual(Selection.objects.count(), 1)
        self.assertIsNone(Selection.objects.filter(id=away_id).first())

    def test_mirror_full_market_mirrors_both_sides(self):
        """With ``mirror_full_market`` (the duel path), the market's opposite
        side is mirrored too, so ``opposite_selection`` can resolve it from the
        local DB — regression for the duel-send 400."""
        home_id = self.selection_id
        away_id = f"{self.event_id}-ml-ft:away-away"
        body = _two_way_markets_response(
            event_id=self.event_id, home_id=home_id, away_id=away_id,
        )
        with self._patch_client(body):
            sel = ensure_chain(self.event_id, home_id, mirror_full_market=True)
        self.assertEqual(sel.id, home_id)
        market_sels = Selection.objects.filter(market_id=f"{self.event_id}-ml-ft")
        self.assertEqual(market_sels.count(), 2)
        away = Selection.objects.filter(id=away_id).first()
        self.assertIsNotNone(away)
        self.assertEqual(away.decimal_odds, Decimal("2.2000"))

    def test_unknown_selection_raises(self):
        """Aggregator returned the event but not the requested selection."""
        body = _markets_response(
            event_id=self.event_id, selection_id="someone-else",
        )
        with self._patch_client(body):
            with self.assertRaises(ChainBuildError):
                ensure_chain(self.event_id, "this-was-not-returned")


@override_settings(USE_AGGRIGATOR=False)
class LegacyFallbackTests(TestCase):
    """When ``USE_AGGRIGATOR=False`` (rollback), ``ensure_chain`` must NOT
    call the aggregator — it falls back to ``Selection.objects.get(pk=...)``
    and surfaces its own ChainBuildError if the row isn't local."""

    def test_legacy_path_uses_local_db(self):
        with patch("core.event.services.aggregator_chain.AggrigatorClient") as MockC:
            with self.assertRaises(ChainBuildError):
                ensure_chain("nonexistent-event", "nonexistent-selection")
            # Aggregator client is never instantiated in legacy mode.
            MockC.assert_not_called()
