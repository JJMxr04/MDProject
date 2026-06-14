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
        # The builder now lives behind a "Create duel" button + modal.
        self.assertContains(resp, 'data-modal-open="#duel-create-modal"')
        self.assertContains(resp, 'data-island="duel-builder"')
        self.assertContains(resp, "Accept the duel challenge")
        self.assertContains(resp, "Finished")

    def test_duels_page_context_pages(self):
        from django.core.paginator import Page
        from django.urls import reverse
        resp = self.client.get(reverse("core-portal:portal-duels"))
        for key in ("challenges", "sent", "accepted", "finished"):
            self.assertIsInstance(resp.context[key], Page)
        record = resp.context["duel_record"]
        self.assertEqual(record["total"], 0)
        self.assertIsNone(record["win_rate"])

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


@override_settings(USE_AGGRIGATOR=False)
class DuelRecordTests(TestCase):
    """`duel_record` / `duel_row` / list helpers — the duel-page read layer."""

    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.league = make_league()

    def _duel(self, home_status=None, away_status=None):
        """Send + accept a fresh duel; optionally settle it. Returns the Match."""
        event = make_event(self.league)
        _, home, away = make_two_way_market(event)
        invite = duels.send_duel(self.challenger, self.opponent, event.id, home.id)
        Invite.objects.accept_invite(invite)
        match = Match.objects.get(match_type="duel", games__event=event)
        if home_status is not None:
            home.settlement_status = home_status
            home.save()
            away.settlement_status = away_status
            away.save()
            match.refresh_from_db()
        return match, home, away

    def test_duel_record_counts_won_lost_draw(self):
        self._duel(SettlementStatus.WON, SettlementStatus.LOST)   # challenger wins
        self._duel(SettlementStatus.LOST, SettlementStatus.WON)   # challenger loses
        self._duel(SettlementStatus.PUSH, SettlementStatus.PUSH)  # draw
        rec = duels.duel_record(self.challenger)
        self.assertEqual(rec["total"], 3)
        self.assertEqual(rec["won"], 1)
        self.assertEqual(rec["lost"], 1)
        self.assertEqual(rec["draw"], 1)
        self.assertEqual(rec["open"], 0)
        self.assertEqual(rec["win_rate"], 50)
        # The opponent sees the mirror image.
        opp = duels.duel_record(self.opponent)
        self.assertEqual(opp["won"], 1)
        self.assertEqual(opp["lost"], 1)

    def test_open_duel_not_counted_as_draw(self):
        self._duel()  # accepted, unsettled
        rec = duels.duel_record(self.challenger)
        self.assertEqual(rec["open"], 1)
        self.assertEqual(rec["draw"], 0)
        self.assertIsNone(rec["win_rate"])

    def test_duel_row_your_side_perspective(self):
        match, home, away = self._duel()
        chal_row = duels.duel_row(match, self.challenger)
        opp_row = duels.duel_row(match, self.opponent)
        self.assertEqual(chal_row["your_side"], home.label)
        self.assertEqual(chal_row["opponent_side"], away.label)
        self.assertEqual(chal_row["status"], "open")
        # Same match, opposite perspective → sides swap.
        self.assertEqual(opp_row["your_side"], away.label)
        self.assertEqual(opp_row["opponent_name"], self.challenger.username)

    def test_finished_and_accepted_lists_split_by_state(self):
        self._duel(SettlementStatus.WON, SettlementStatus.LOST)  # finished
        self._duel()  # in progress
        self.assertEqual(duels.accepted_duels(self.challenger).count(), 1)
        self.assertEqual(duels.finished_duels(self.challenger).count(), 1)

    def test_outgoing_duel_invites_pending_then_clears_on_accept(self):
        event = make_event(self.league)
        _, home, _ = make_two_way_market(event)
        invite = duels.send_duel(self.challenger, self.opponent, event.id, home.id)
        # Visible to the sender as pending, not to the recipient's sent list.
        self.assertIn(invite, list(duels.outgoing_duel_invites(self.challenger)))
        self.assertEqual(list(duels.outgoing_duel_invites(self.opponent)), [])
        # Once accepted it's a Match, so it leaves the pending list.
        Invite.objects.accept_invite(invite)
        self.assertEqual(list(duels.outgoing_duel_invites(self.challenger)), [])

    def test_incoming_duel_invites_excludes_expired_and_non_duels(self):
        # A live duel invite is visible to the opponent.
        event = make_event(self.league)
        _, home, _ = make_two_way_market(event)
        live = duels.send_duel(self.challenger, self.opponent, event.id, home.id)
        self.assertIn(live, list(duels.incoming_duel_invites(self.opponent)))

        # An expired duel invite drops out.
        ev2 = make_event(self.league)
        _, home2, _ = make_two_way_market(ev2)
        expired = duels.send_duel(self.challenger, self.opponent, ev2.id, home2.id)
        Invite.objects.filter(pk=expired.pk).update(expires_at=_past())
        self.assertNotIn(expired, list(duels.incoming_duel_invites(self.opponent)))

        # A non-duel match invite is excluded (payload.duel filter). Created
        # directly to avoid the manager's match-invite email path.
        Invite.objects.create(
            player=self.opponent, sender=self.challenger,
            type="match", state="sent", payload={"duel": False},
        )
        ids = {i.pk for i in duels.incoming_duel_invites(self.opponent)}
        self.assertEqual(ids, {live.pk})


@override_settings(USE_AGGRIGATOR=False)
class DuelPagePaginationTests(TestCase):
    def setUp(self):
        self.challenger = make_user("challenger")
        self.opponent = make_user("opponent")
        self.challenger.add_friend(self.opponent)
        self.client.force_login(self.challenger)
        self.league = make_league()

    def test_incoming_challenge_renders_accept_buttons(self):
        from django.urls import reverse
        event = make_event(self.league)
        _, home, _ = make_two_way_market(event)
        duels.send_duel(self.challenger, self.opponent, event.id, home.id)
        self.client.force_login(self.opponent)
        resp = self.client.get(reverse("core-portal:portal-duels"))
        self.assertContains(resp, 'id="invite-list"')
        self.assertContains(resp, 'data-action="invite-act"')
        self.assertContains(resp, "challenged you to a duel")

    def test_finished_list_paginates_at_10(self):
        from django.urls import reverse
        for _ in range(11):
            event = make_event(self.league)
            _, home, away = make_two_way_market(event)
            invite = duels.send_duel(self.challenger, self.opponent, event.id, home.id)
            Invite.objects.accept_invite(invite)
            home.settlement_status = SettlementStatus.WON
            home.save()
            away.settlement_status = SettlementStatus.LOST
            away.save()
        url = reverse("core-portal:portal-duels")
        page1 = self.client.get(url)
        self.assertEqual(len(page1.context["finished_rows"]), 10)
        page2 = self.client.get(url, {"fpage": 2})
        self.assertEqual(len(page2.context["finished_rows"]), 1)


@override_settings(USE_AGGRIGATOR=False)
class DuelCapTests(TestCase):
    """A player may hold at most MAX_ACTIVE_DUELS concurrent in-progress duels
    (both roles); the cap is enforced when a duel is accepted, not sent."""

    def setUp(self):
        self.a = make_user("a")
        self.b = make_user("b")
        self.a.add_friend(self.b)
        self.league = make_league()

    def _fill_active_duels(self, user, n, state="accepted"):
        # Lightweight stand-ins for in-progress duels (player_1 role is enough —
        # active_duel_count counts both roles).
        for _ in range(n):
            Match.objects.create(player_1=user, match_type="duel", match_state=state)

    def _send(self):
        event = make_event(self.league)
        _, home, _ = make_two_way_market(event)
        return duels.send_duel(self.a, self.b, event.id, home.id)

    def test_accept_blocked_when_accepter_at_cap(self):
        self._fill_active_duels(self.b, duels.MAX_ACTIVE_DUELS)
        invite = self._send()
        with self.assertRaises(duels.DuelError):
            Invite.objects.accept_invite(invite)
        invite.refresh_from_db()
        self.assertEqual(invite.state, "sent")  # rolled back, still acceptable

    def test_accept_blocked_when_challenger_at_cap(self):
        self._fill_active_duels(self.a, duels.MAX_ACTIVE_DUELS)
        invite = self._send()
        with self.assertRaises(duels.DuelError):
            Invite.objects.accept_invite(invite)

    def test_completed_duels_do_not_count(self):
        self._fill_active_duels(self.b, duels.MAX_ACTIVE_DUELS, state="completed")
        invite = self._send()
        Invite.objects.accept_invite(invite)  # completed don't count → allowed
        self.assertTrue(
            Match.objects.filter(match_type="duel", player_2=self.b, match_state="accepted").exists()
        )

    def test_accept_allowed_just_under_cap(self):
        self._fill_active_duels(self.b, duels.MAX_ACTIVE_DUELS - 1)
        invite = self._send()
        Invite.objects.accept_invite(invite)  # brings b to exactly the cap
        self.assertEqual(duels.active_duel_count(self.b), duels.MAX_ACTIVE_DUELS)

    def test_sending_is_not_capped(self):
        # Sending stays open even when in-progress duels are at the cap.
        self._fill_active_duels(self.b, duels.MAX_ACTIVE_DUELS)
        invite = self._send()  # must not raise
        self.assertEqual(invite.state, "sent")

    def test_accept_locks_player_rows(self):
        # The cap check + create must serialize per player: accepting a duel
        # acquires a SELECT ... FOR UPDATE on both players' User rows so two
        # concurrent accepts can't both slip past the cap.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from core.user.models import User

        invite = self._send()
        with CaptureQueriesContext(connection) as ctx:
            Invite.objects.accept_invite(invite)
        table = User._meta.db_table
        locked = [
            q["sql"] for q in ctx.captured_queries
            if "for update" in q["sql"].lower() and table in q["sql"].lower()
        ]
        self.assertTrue(locked, "expected SELECT ... FOR UPDATE on the user table")


def _catalog(items):
    from unittest.mock import MagicMock, patch
    client = MagicMock()
    client.list_events.return_value = {"items": items}
    return patch(
        "core.event.providers.aggregator_client.AggrigatorClient",
        return_value=client,
    )


def _priced_items(n):
    return [
        {"id": f"evt-{i}", "markets": [{
            "category": "MONEYLINE", "scope": "FULL_GAME",
            "selections": [{"id": f"evt-{i}-ml:home", "type": "HOME", "decimal_odds": "1.90"}],
        }]}
        for i in range(n)
    ]


@override_settings(USE_AGGRIGATOR=False)
class DuelMatchIndependenceTests(TestCase):
    """Duels and matches are independent challenges — a pending duel must not
    be mistaken for a pending match (the dedup excludes duels)."""

    def setUp(self):
        self.a = make_user("a")
        self.b = make_user("b")
        self.a.add_friend(self.b)
        self.league = make_league()

    def test_pending_duel_does_not_block_private_match(self):
        from django.urls import reverse

        event = make_event(self.league)
        _, home, _ = make_two_way_market(event)
        duel_invite = duels.send_duel(self.a, self.b, event.id, home.id)

        self.client.force_login(self.a)
        with _catalog(_priced_items(6)):  # satisfy the MARATHON fixture gate
            r = self.client.post(
                reverse("core-portal:portal-create-public-match"),
                {"type": "private", "player": str(self.b.id), "format": "MARATHON"},
            )
        self.assertEqual(r.status_code, 200)
        # A NEW match invite was created — the duel was not returned as a dupe.
        self.assertNotEqual(str(r.json()["invite_id"]), str(duel_invite.id))
        self.assertEqual(
            Invite.objects.filter(sender=self.a, player=self.b, type="match")
            .exclude(payload__has_key="duel").count(),
            1,
        )

    def test_pair_has_no_match_uniqueness(self):
        # A tournament must be able to pair two users who already have a
        # personal match — Match carries no (player_1, player_2) uniqueness.
        m1 = Match.objects.create(player_1=self.a, player_2=self.b, match_type="private", match_state="accepted")
        m2 = Match.objects.create(player_1=self.a, player_2=self.b, match_type="public", match_state="accepted")
        self.assertNotEqual(m1.id, m2.id)
        self.assertEqual(Match.objects.filter(player_1=self.a, player_2=self.b).count(), 2)


def _past():
    from datetime import timedelta
    from django.utils import timezone
    return timezone.now() - timedelta(hours=1)
