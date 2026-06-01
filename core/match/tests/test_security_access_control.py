"""Cross-user access-control (IDOR) denial tests — Phase 0 security fixes.

Each test asserts that a logged-in user who is NOT the owner/participant of an
object is denied (404/403), per the findings register:

- S-4b  public_match_detail_view leaks any match by id
- S-5   player_2_select_outcome / pick_on_locked_slot / event_markets leak/act
        on games the requester isn't a player in
- S-15  player_in_game_required decorator logic

We build the object graph directly (Match.objects.create + Game.objects.create_game)
rather than via Match.objects.create_match — the latter seeds a Golden Game by
calling the aggregator at localhost:8001, which isn't available in unit tests.
These access-control checks happen *before* any aggregator work, so the minimal
graph is sufficient and keeps the test hermetic.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from core.game.models import Game
from core.match.models import Match
from core.match.tests.factories import make_user


def _make_match(p1, p2, *, state="accepted", match_type="private") -> Match:
    return Match.objects.create(
        player_1=p1, player_2=p2, match_state=state, match_type=match_type
    )


def _make_game(match) -> Game:
    # create_game also makes the Bet row; no event needed for access checks.
    return Game.objects.create_game(
        match=match, owner=match.player_1, player_2=match.player_2, slot=1
    )


class PublicMatchDetailAccessTests(TestCase):
    """S-4b: the public join page must not expose non-public matches to
    non-participants."""

    def test_non_participant_cannot_view_accepted_match(self):
        p1, p2, outsider = make_user("p1"), make_user("p2"), make_user("out")
        match = _make_match(p1, p2, state="accepted")

        self.client.force_login(outsider)
        url = reverse("core-portal:portal-public-match-detail", args=[match.id])
        resp = self.client.get(url, secure=True)
        # The view raises Http404; the project's custom handler404
        # (core.views.portal_or_404) rewrites portal 404s into a 302->"/" so it
        # doesn't even confirm the URL exists. Either way the denial contract is:
        # NOT 200, and the match is never rendered.
        self.assertIn(resp.status_code, (302, 404))

    def test_participant_can_view_their_accepted_match(self):
        p1, p2 = make_user("p1"), make_user("p2")
        match = _make_match(p1, p2, state="accepted")

        self.client.force_login(p1)
        url = reverse("core-portal:portal-public-match-detail", args=[match.id])
        self.assertEqual(self.client.get(url, secure=True).status_code, 200)

    def test_anyone_can_view_open_public_match(self):
        owner, viewer = make_user("owner"), make_user("viewer")
        match = Match.objects.create(
            player_1=owner, match_state="created", match_type="public"
        )

        self.client.force_login(viewer)
        url = reverse("core-portal:portal-public-match-detail", args=[match.id])
        self.assertEqual(self.client.get(url, secure=True).status_code, 200)  # joinable -> visible


class GameEndpointAccessTests(TestCase):
    """S-5 / S-15: game-scoped endpoints must reject non-players (403 from the
    player_in_game_required decorator) before doing anything."""

    def setUp(self):
        self.p1, self.p2, self.outsider = (
            make_user("p1"), make_user("p2"), make_user("out"),
        )
        self.match = _make_match(self.p1, self.p2, state="accepted")
        self.game = _make_game(self.match)

    def test_event_markets_denies_non_player(self):
        self.client.force_login(self.outsider)
        url = reverse("core-portal:portal-match-event-market", args=[self.game.id])
        self.assertEqual(self.client.get(url, secure=True).status_code, 403)

    def test_event_markets_allows_player(self):
        self.client.force_login(self.p1)
        url = reverse("core-portal:portal-match-event-market", args=[self.game.id])
        self.assertEqual(self.client.get(url, secure=True).status_code, 200)

    def test_player_2_select_outcome_denies_non_player(self):
        self.client.force_login(self.outsider)
        url = reverse(
            "core-portal:portal-match-game-player_2_select_outcome", args=[self.game.id]
        )
        resp = self.client.post(url, data="{}", content_type="application/json", secure=True)
        self.assertEqual(resp.status_code, 403)

    def test_pick_on_locked_slot_denies_non_player(self):
        self.client.force_login(self.outsider)
        url = reverse("core-portal:portal-match-game-pick-locked", args=[self.game.id])
        resp = self.client.post(url, data="{}", content_type="application/json", secure=True)
        self.assertEqual(resp.status_code, 403)
