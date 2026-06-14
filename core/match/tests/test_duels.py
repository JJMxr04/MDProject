"""Phase 14 — duels: send validation, accept shape, settlement (win/draw).

A duel is one game, two players, opposite sides, settling when the event ends.
ensure_chain returns the local Selection with USE_AGGRIGATOR off, so the whole
flow runs without touching the aggregator.
"""

from __future__ import annotations

from django.test import TestCase, override_settings

from core.event.models import MarketCategory
from core.event.models.odds.selection import SettlementStatus
from core.mail.models import Invite
from core.mail.models.invites import InviteExpired
from core.mail.models.notifications import Notification
from core.match import duels
from core.match.models import Match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_market,
    make_selection,
    make_two_way_market,
    make_user,
)


@override_settings(USE_AGGRIGATOR=False)
class DuelSendTests(TestCase):
    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.league = make_league()
        self.event = make_event(self.league)  # start_time = now + 2 days
        self.market, self.home, self.away = make_two_way_market(self.event)

    def test_send_creates_duel_invite_with_opposite_side(self):
        invite = duels.send_duel(self.challenger, self.opponent, self.event.id, self.home.id)
        self.assertEqual(invite.type, "match")
        self.assertTrue(invite.payload["duel"])
        self.assertEqual(invite.payload["selection_id"], self.home.id)
        self.assertEqual(invite.payload["opposite_selection_id"], self.away.id)
        # Expires at kickoff (D-14 #3).
        self.assertEqual(invite.expires_at, self.event.start_time)
        self.assertEqual(invite.player, self.opponent)

    def test_three_way_market_is_rejected(self):
        market = make_market(self.event, category=MarketCategory.MONEYLINE)
        home = make_selection(market, selection_type="HOME")
        make_selection(market, selection_type="DRAW")
        make_selection(market, selection_type="AWAY")
        with self.assertRaises(duels.DuelError):
            duels.send_duel(self.challenger, self.opponent, self.event.id, home.id)

    def test_started_event_is_rejected(self):
        past = make_event(self.league, start_time=_past())
        _, home, _ = make_two_way_market(past)
        with self.assertRaises(duels.DuelError):
            duels.send_duel(self.challenger, self.opponent, past.id, home.id)

    def test_non_friend_is_rejected(self):
        stranger = make_user("stranger")
        with self.assertRaises(duels.DuelError):
            duels.send_duel(self.challenger, stranger, self.event.id, self.home.id)

    def test_self_duel_is_rejected(self):
        with self.assertRaises(duels.DuelError):
            duels.send_duel(self.challenger, self.challenger, self.event.id, self.home.id)


@override_settings(USE_AGGRIGATOR=False)
class DuelAcceptTests(TestCase):
    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.league = make_league()
        self.event = make_event(self.league)
        self.market, self.home, self.away = make_two_way_market(self.event)
        self.invite = duels.send_duel(
            self.challenger, self.opponent, self.event.id, self.home.id,
        )

    def _accept(self):
        Invite.objects.accept_invite(self.invite)
        return Match.objects.get(match_type="duel", player_1=self.challenger)

    def test_accept_builds_degenerate_match_with_both_sides(self):
        match = self._accept()
        self.assertEqual(match.match_state, "accepted")
        self.assertEqual(match.player_2, self.opponent)
        self.assertEqual(match.end_date, self.event.start_time)
        # Exactly one game, not golden, both sides set on its bet.
        games = list(match.games.all())
        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertFalse(game.is_golden)
        self.assertEqual(game.bet.owner_outcome_id, self.home.id)
        self.assertEqual(game.bet.player_2_outcome_id, self.away.id)
        self.assertEqual(game.bet.locked_market_id, self.market.id)
        # No Golden Game, no tiebreaker.
        self.assertIsNone(match.games.filter(is_golden=True).first())
        self.assertIsNone(match.tiebreaker)

    def test_accept_after_expiry_is_blocked(self):
        # Simulate time passing to kickoff: the invite is now past its window.
        Invite.objects.filter(pk=self.invite.pk).update(expires_at=_past())
        self.invite.refresh_from_db()
        with self.assertRaises(InviteExpired):
            Invite.objects.accept_invite(self.invite)
        self.assertFalse(Match.objects.filter(match_type="duel").exists())


@override_settings(USE_AGGRIGATOR=False)
class DuelSettlementTests(TestCase):
    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.league = make_league()
        self.event = make_event(self.league)
        self.market, self.home, self.away = make_two_way_market(self.event)
        invite = duels.send_duel(self.challenger, self.opponent, self.event.id, self.home.id)
        Invite.objects.accept_invite(invite)
        self.match = Match.objects.get(match_type="duel", player_1=self.challenger)

    def _settle(self, home_status, away_status):
        self.home.settlement_status = home_status
        self.home.save()  # post_save signal completes the duel
        self.away.settlement_status = away_status
        self.away.save()
        self.match.refresh_from_db()

    def test_challenger_side_wins(self):
        self._settle(SettlementStatus.WON, SettlementStatus.LOST)
        self.assertEqual(self.match.match_state, "completed")
        self.assertEqual(self.match.winner, self.challenger)

    def test_opponent_side_wins(self):
        self._settle(SettlementStatus.LOST, SettlementStatus.WON)
        self.assertEqual(self.match.match_state, "completed")
        self.assertEqual(self.match.winner, self.opponent)

    def test_push_settles_as_draw(self):
        self._settle(SettlementStatus.PUSH, SettlementStatus.PUSH)
        self.assertEqual(self.match.match_state, "completed")
        self.assertIsNone(self.match.winner)

    def test_void_settles_as_draw(self):
        self._settle(SettlementStatus.VOID, SettlementStatus.VOID)
        self.assertEqual(self.match.match_state, "completed")
        self.assertIsNone(self.match.winner)

    def test_pending_side_keeps_duel_open(self):
        self.home.settlement_status = SettlementStatus.WON
        self.home.save()
        self.match.refresh_from_db()
        # The other side is still PENDING — not decided yet.
        self.assertEqual(self.match.match_state, "accepted")
        self.assertIsNone(self.match.winner)

    def test_settlement_notifies_both_players_once(self):
        before = Notification.objects.count()
        self._settle(SettlementStatus.WON, SettlementStatus.LOST)
        # One result Notification per player (challenger won, opponent lost).
        new = Notification.objects.count() - before
        self.assertGreaterEqual(new, 2)
        self.assertTrue(
            Notification.objects.filter(user=self.challenger, message__icontains="won").exists()
        )


@override_settings(USE_AGGRIGATOR=False)
class DuelSendViewTests(TestCase):
    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.client.force_login(self.challenger)
        self.league = make_league()
        self.event = make_event(self.league)
        self.market, self.home, self.away = make_two_way_market(self.event)

    def test_send_endpoint_creates_invite(self):
        import json
        from django.urls import reverse
        resp = self.client.post(
            reverse("core-portal:portal-match-duel-send"),
            data=json.dumps({
                "event_id": self.event.id,
                "selection_id": self.home.id,
                "opponent_id": str(self.opponent.public_id),
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(Invite.objects.filter(sender=self.challenger, player=self.opponent).exists())

    def test_send_endpoint_rejects_three_way(self):
        import json
        from django.urls import reverse
        market = make_market(self.event)
        home = make_selection(market, selection_type="HOME")
        make_selection(market, selection_type="DRAW")
        make_selection(market, selection_type="AWAY")
        resp = self.client.post(
            reverse("core-portal:portal-match-duel-send"),
            data=json.dumps({
                "event_id": self.event.id,
                "selection_id": home.id,
                "opponent_id": str(self.opponent.public_id),
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


@override_settings(USE_AGGRIGATOR=False)
class DuelPageTests(TestCase):
    def setUp(self):
        self.user = make_user("dueler")
        self.client.force_login(self.user)

    def test_duels_page_renders(self):
        from django.urls import reverse
        resp = self.client.get(reverse("core-portal:portal-duels"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Duel a friend")
        self.assertContains(resp, 'data-island="duel-builder"')

    def test_events_endpoint_shapes_upcoming_events(self):
        from unittest.mock import MagicMock, patch
        from django.urls import reverse

        client = MagicMock()
        client.list_events.return_value = {"items": [{
            "id": "evt-1",
            "home_team": {"name": "Arsenal"},
            "away_team": {"name": "Chelsea"},
            "league": {"name": "EPL"},
            "start_time": "2026-07-01T15:00:00Z",
        }]}
        with patch("core.event.providers.aggregator_client.AggrigatorClient", return_value=client):
            resp = self.client.get(reverse("core-portal:portal-match-duel-events"))
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        self.assertEqual(items[0]["event_id"], "evt-1")
        self.assertEqual(items[0]["label"], "Chelsea @ Arsenal")

    def test_events_endpoint_requires_login(self):
        from django.urls import reverse
        self.client.logout()
        resp = self.client.get(reverse("core-portal:portal-match-duel-events"))
        self.assertEqual(resp.status_code, 302)


def _past():
    from datetime import timedelta
    from django.utils import timezone
    return timezone.now() - timedelta(hours=1)
