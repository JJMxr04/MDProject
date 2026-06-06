"""Match creation/acceptance gate — no events with markets → no match.

A match whose window has nothing a Golden Game could seed against is dead
on arrival: nobody could complete an accept. So creation is blocked up
front (public create views + manager) and acceptance keeps its existing
atomic raise. The private create+accept path now rolls back the Match row
too instead of leaking a stray ``created`` match.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from core.game.models.game import GoldenGameUnavailable
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


class PublicCreateGateTests(TestCase):
    def setUp(self):
        self.user = make_user("creator")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:portal-create-public-match")

    def test_create_blocked_when_no_events(self):
        with patch_catalog([]):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("No events", r.json()["message"])
        self.assertEqual(Match.objects.count(), 0)

    def test_create_blocked_when_events_lack_markets(self):
        with patch_catalog([{"id": "evt-1", "markets": []}]):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("markets", r.json()["message"])
        self.assertEqual(Match.objects.count(), 0)

    def test_create_succeeds_when_catalog_has_markets(self):
        candidate = [{
            "id": "evt-ok",
            "markets": [{
                "category": "MONEYLINE", "scope": "FULL_GAME",
                "selections": [
                    {"id": "evt-ok-ml:home", "type": "HOME", "decimal_odds": "1.90"},
                ],
            }],
        }]
        with patch_catalog(candidate):
            r = self.client.post(self.url, {"type": "public"})
        self.assertEqual(r.status_code, 200)
        match = Match.objects.get()
        self.assertEqual(match.match_state, "created")
        self.assertEqual(match.player_1, self.user)
        self.assertIsNone(match.player_2)


class PrivateCreateRollbackTests(TestCase):
    def test_failed_golden_seed_rolls_back_match_row(self):
        """create_match(p1, p2) with an empty catalog must leave NOTHING —
        previously the Match row leaked in 'created' state and showed up in
        the public join list."""
        p1 = make_user("p1")
        p2 = make_user("p2")
        with patch_catalog([]):
            with self.assertRaises(GoldenGameUnavailable):
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
