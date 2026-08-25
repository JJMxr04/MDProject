"""Match creation/acceptance gate — no events with markets → no match.

A match whose window has nothing a Golden Game could seed against is dead
on arrival: nobody could complete an accept. So creation is blocked up
front (public create views + manager) and acceptance keeps its existing
atomic raise. The private create+accept path now rolls back the Match row
too instead of leaking a stray ``created`` match.

With format presets, the gate is the fixture-availability check:
``assert_window_viable`` runs FIRST in ``create_match`` and raises
``FixtureUnavailable`` ("Only N games available in this window …") when the
window holds fewer distinct priced events than the format needs
(``games_per_player + 1``; default MARATHON → 6).
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from core.game.models.game import FixtureUnavailable
from core.match.models import Match
from core.match.tests.factories import make_match, make_user


def patch_catalog(items):
    """Patch the aggregator listing to return exactly ``items``."""
    client = MagicMock()
    client.list_events.return_value = {"items": items}
    return patch(
        "core.event.providers.aggregator_client.AggrigatorClient",
        return_value=client,
    )


def priced_items(n, prefix="evt"):
    """``n`` distinct events, each with one priced MONEYLINE market —
    the minimal shape ``count_available_events`` counts as available."""
    return [
        {
            "id": f"{prefix}-{i}",
            "markets": [{
                "category": "MONEYLINE", "scope": "FULL_GAME",
                "selections": [{
                    "id": f"{prefix}-{i}-ml:home",
                    "type": "HOME",
                    "decimal_odds": "1.90",
                }],
            }],
        }
        for i in range(n)
    ]


class PublicCreateGateTests(TestCase):
    def setUp(self):
        self.user = make_user("creator")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:portal-create-public-match")

    def test_create_blocked_when_no_events(self):
        with patch_catalog([]):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Only 0 games", r.json()["message"])
        self.assertEqual(Match.objects.count(), 0)

    def test_create_blocked_when_events_lack_markets(self):
        # An event with no priced market can't host a pick — counts as 0.
        with patch_catalog([{"id": "evt-1", "markets": []}]):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Only 0 games", r.json()["message"])
        self.assertEqual(Match.objects.count(), 0)

    def test_create_succeeds_when_catalog_has_markets(self):
        # Default format is MARATHON → needs 6 distinct priced events
        # (5 games per player + the shared Golden Game).
        with patch_catalog(priced_items(6)):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 200)
        match = Match.objects.get()
        self.assertEqual(match.match_state, "created")
        self.assertEqual(match.player_1, self.user)
        self.assertIsNone(match.player_2)


class PrivateCreateRollbackTests(TestCase):
    def test_failed_availability_gate_rolls_back_match_row(self):
        """create_match(p1, p2) with an empty catalog must leave NOTHING —
        previously the Match row leaked in 'created' state and showed up in
        the public join list. The empty window now trips the fixture-
        availability gate (FixtureUnavailable) before anything is written."""
        p1 = make_user("p1")
        p2 = make_user("p2")
        with patch_catalog([]):
            with self.assertRaises(FixtureUnavailable):
                Match.objects.create_match(player_1=p1, player_2=p2)
        self.assertEqual(Match.objects.count(), 0)


class AcceptGateTests(TestCase):
    def test_accept_blocked_when_no_events(self):
        """An open match (created while the catalog was healthy) can't be
        accepted once the catalog has nothing to seed — the accept rolls
        back and the match stays open."""
        p1 = make_user("p1")
        joiner = make_user("joiner")
        match = make_match(p1, None, accept=False)

        self.client.force_login(joiner)
        url = reverse("core-portal:portal-accept-public-match", args=[match.id])
        with patch_catalog([]):
            r = self.client.post(
                url, data=json.dumps({"action": "accept"}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 400)
        match.refresh_from_db()
        self.assertEqual(match.match_state, "created")
        self.assertIsNone(match.player_2)
        self.assertEqual(match.games.count(), 0)
