"""Phase 9 — opponent scouting.

``scout_user`` computes tendencies from a user's actual MATCH picks (MDProject
gameplay — Game/Bet/Selection), and the match-detail page PRO-gates the card.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.billing.models import Plan, Subscription
from core.event.models import MarketCategory
from core.event.models.odds.selection import SettlementStatus
from core.game.models import Bet, Game
from core.match import scouting
from core.match.models import Match
from core.match.tests.factories import (
    make_event,
    make_league,
    make_market,
    make_selection,
    make_user,
)
from core.metrics.models import ProductEvent


class ScoutUserQueryTests(TestCase):
    """The data layer reads real match picks, not the aggregator bet table."""

    def setUp(self):
        self.user = make_user("scouted")
        self.other = make_user("viewer")
        self.league = make_league()

    def _add_pick(self, *, sel_type, status, odds="1.50", category=MarketCategory.MONEYLINE):
        """One settled pick owned by self.user (regular slot shape)."""
        event = make_event(self.league)
        market = make_market(event, category=category)
        sel = make_selection(market, selection_type=sel_type, odds=odds, settlement_status=status)
        bet = Bet.objects.create_bet()
        Bet.objects.set_owner_outcome(bet, sel)
        match = Match.objects.create(
            player_1=self.user, player_2=self.other,
            match_type="private", match_state="accepted",
        )
        Game.objects.create(
            match=match, owner=self.user, player_2=self.other,
            slot=1, is_golden=False, event=event, bet=bet,
        )
        return sel

    def test_insufficient_history(self):
        for _ in range(2):
            self._add_pick(sel_type="HOME", status=SettlementStatus.WON)
        out = scouting.scout_user(self.user)
        self.assertEqual(out["reason"], "insufficient_history")
        self.assertEqual(out["settled_picks"], 2)

    def test_tendencies_from_match_picks(self):
        W, L = SettlementStatus.WON, SettlementStatus.LOST
        # 4 home (3W/1L), 1 away (W), 1 over (W), 1 under (L).
        self._add_pick(sel_type="HOME", status=W, odds="1.50")
        self._add_pick(sel_type="HOME", status=W, odds="1.50")
        self._add_pick(sel_type="HOME", status=W, odds="2.50")
        self._add_pick(sel_type="HOME", status=L, odds="1.50")
        self._add_pick(sel_type="AWAY", status=W, odds="2.50")
        self._add_pick(sel_type="OVER", status=W, odds="1.90", category=MarketCategory.TOTAL)
        self._add_pick(sel_type="UNDER", status=L, odds="1.90", category=MarketCategory.TOTAL)

        out = scouting.scout_user(self.user)
        self.assertIsNone(out["reason"])
        self.assertEqual(out["settled_picks"], 7)
        self.assertEqual(out["wins"], 5)
        self.assertEqual(out["losses"], 2)
        self.assertEqual(out["hit_rate"], round(5 / 7, 3))
        self.assertEqual(out["side"], {"home": 4, "away": 1})
        self.assertEqual(out["over_under"], {"over": 1, "under": 1})
        self.assertEqual(out["fav_dog"], {"favorite": 5, "underdog": 2})
        markets = {m["key"]: m for m in out["markets"]}
        self.assertEqual(markets["moneyline"]["picks"], 5)
        self.assertEqual(markets["total"]["picks"], 2)
        self.assertEqual(len(out["recent_form"]), 7)

    def test_recent_form_label_is_humanized(self):
        """Recent-form tooltips show the plain-English pick, not the raw
        'home home' moneyline label."""
        for _ in range(scouting.MIN_PICKS):
            sel = self._add_pick(sel_type="HOME", status=SettlementStatus.WON)
            sel.label = "home home"
            sel.save()
        out = scouting.scout_user(self.user)
        labels = {f["label"] for f in out["recent_form"]}
        self.assertEqual(labels, {"Home Team Test to win"})

    def test_markets_breakdown_applies_floor(self):
        W, L = SettlementStatus.WON, SettlementStatus.LOST
        # Moneyline: 4 decided (3W/1L) — above the floor, win_rate shown.
        self._add_pick(sel_type="HOME", status=W, category=MarketCategory.MONEYLINE)
        self._add_pick(sel_type="HOME", status=W, category=MarketCategory.MONEYLINE)
        self._add_pick(sel_type="HOME", status=W, category=MarketCategory.MONEYLINE)
        self._add_pick(sel_type="AWAY", status=L, category=MarketCategory.MONEYLINE)
        # Total: 2 decided — below the floor, win_rate suppressed as noise.
        self._add_pick(sel_type="OVER", status=W, category=MarketCategory.TOTAL)
        self._add_pick(sel_type="UNDER", status=L, category=MarketCategory.TOTAL)

        markets = {m["key"]: m for m in scouting.scout_user(self.user)["markets"]}
        self.assertEqual(markets["moneyline"]["market"], "Moneyline")
        self.assertEqual((markets["moneyline"]["wins"], markets["moneyline"]["losses"]), (3, 1))
        self.assertEqual(markets["moneyline"]["win_rate"], round(3 / 4, 3))
        self.assertEqual(markets["total"]["picks"], 2)
        self.assertIsNone(markets["total"]["win_rate"])  # below floor

    def _add_golden_pick(self, *, sel_type, status, as_player_1=True):
        """A pick on an ownerless Golden Game (sides are player_1/player_2)."""
        event = make_event(self.league)
        market = make_market(event)
        sel = make_selection(market, selection_type=sel_type, settlement_status=status)
        bet = Bet.objects.create_bet()
        if as_player_1:
            Bet.objects.set_owner_outcome(bet, sel)
            match = Match.objects.create(player_1=self.user, player_2=self.other, match_type="private", match_state="accepted")
        else:
            Bet.objects.set_player_2_outcome(bet, sel)
            match = Match.objects.create(player_1=self.other, player_2=self.user, match_type="private", match_state="accepted")
        Game.objects.create(match=match, owner=None, player_2=None, slot=1, is_golden=True, event=event, bet=bet)

    def _add_duel_opponent_pick(self, *, sel_type, status):
        """The opponent's side of a duel (user is player_2 → player_2_outcome)."""
        event = make_event(self.league)
        market = make_market(event)
        sel = make_selection(market, selection_type=sel_type, settlement_status=status)
        bet = Bet.objects.create_bet()
        Bet.objects.set_player_2_outcome(bet, sel)
        match = Match.objects.create(player_1=self.other, player_2=self.user, match_type="duel", match_state="accepted")
        Game.objects.create(match=match, owner=self.other, player_2=self.user, slot=1, is_golden=False, event=event, bet=bet)

    def test_includes_golden_game_pick(self):
        for _ in range(4):
            self._add_pick(sel_type="HOME", status=SettlementStatus.WON)
        self._add_golden_pick(sel_type="OVER", status=SettlementStatus.WON, as_player_1=True)
        out = scouting.scout_user(self.user)
        self.assertEqual(out["settled_picks"], 5)
        self.assertEqual(out["over_under"]["over"], 1)  # golden pick counted

    def test_includes_golden_pick_when_player_2(self):
        for _ in range(4):
            self._add_pick(sel_type="HOME", status=SettlementStatus.WON)
        self._add_golden_pick(sel_type="UNDER", status=SettlementStatus.WON, as_player_1=False)
        out = scouting.scout_user(self.user)
        self.assertEqual(out["settled_picks"], 5)
        self.assertEqual(out["over_under"]["under"], 1)  # player_2 golden side counted

    def test_includes_duel_opponent_pick(self):
        for _ in range(4):
            self._add_pick(sel_type="HOME", status=SettlementStatus.WON)
        self._add_duel_opponent_pick(sel_type="AWAY", status=SettlementStatus.WON)
        out = scouting.scout_user(self.user)
        self.assertEqual(out["settled_picks"], 5)
        self.assertEqual(out["side"]["away"], 1)  # duel opponent side counted

    def test_does_not_count_opponents_picks(self):
        # 5 picks for self.user; the opponent's own owned game must not leak in.
        for _ in range(5):
            self._add_pick(sel_type="AWAY", status=SettlementStatus.WON)
        # An opponent-owned game in a shared match.
        event = make_event(self.league)
        market = make_market(event)
        sel = make_selection(market, selection_type="HOME", settlement_status=SettlementStatus.WON)
        bet = Bet.objects.create_bet()
        Bet.objects.set_owner_outcome(bet, sel)
        match = Match.objects.create(player_1=self.other, player_2=self.user, match_type="private", match_state="accepted")
        Game.objects.create(match=match, owner=self.other, player_2=self.user, slot=1, is_golden=False, event=event, bet=bet)

        out = scouting.scout_user(self.user)
        self.assertEqual(out["settled_picks"], 5)
        self.assertEqual(out["side"], {"home": 0, "away": 5})  # opponent's HOME pick excluded


_SCOUT = {
    "reason": None, "total_picks": 7, "settled_picks": 7,
    "wins": 5, "losses": 2, "pushes": 0, "hit_rate": 0.714,
    "side": {"home": 4, "away": 1},
    "over_under": {"over": 1, "under": 1},
    "fav_dog": {"favorite": 5, "underdog": 2},
    "markets": [{"key": "moneyline", "market": "Moneyline", "picks": 5,
                 "wins": 4, "losses": 1, "win_rate": 0.8}],
    "leagues": [{"league": "NBA", "picks": 5, "wins": 3, "losses": 2}],
    "recent_form": [{"type": "HOME", "result": "WON", "label": "x"}],
}
_SCOUT_FN = "core.match.scouting.scout_user"


def _make_pro(user):
    plan = Plan.objects.create(code="PRO", name="Pro", amount_cents=900, features={"analytics": True})
    Subscription.objects.update_or_create(user=user, defaults={"plan": plan, "status": "active"})


@override_settings(STRIPE_SECRET_KEY="")
class ScoutingCardTests(TestCase):
    def setUp(self):
        from core.match.tests.factories import make_match
        self.p1 = make_user("p1")
        self.p2 = make_user("p2")
        self.match = make_match(self.p1, self.p2)
        self.url = reverse("core-portal:portal-my-match-detail", args=[self.match.id])

    def _make_pro(self, user):
        _make_pro(user)

    def test_pro_user_sees_opponent_tendencies(self):
        self._make_pro(self.p1)
        self.client.force_login(self.p1)
        with mock.patch(_SCOUT_FN, return_value=_SCOUT) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_called_once_with(self.p2)
        self.assertContains(r, f"Scouting {self.p2.username}")
        self.assertContains(r, "5–2")
        self.assertContains(r, "71%")
        self.assertContains(r, "NBA 3–2")
        self.assertContains(r, "Moneyline 4–1")
        self.assertFalse(ProductEvent.objects.filter(name="paywall_viewed").exists())

    def test_free_user_sees_upsell_and_emits_paywall_viewed(self):
        self.client.force_login(self.p1)
        with mock.patch(_SCOUT_FN) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_not_called()
        self.assertContains(r, "Upgrade to PRO")
        self.assertContains(r, "src=opponent_scouting")
        evt = ProductEvent.objects.filter(name="paywall_viewed").first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.props.get("feature"), "opponent_scouting")

    def test_stranded_payer_sees_refresh_not_pay_again(self):
        # A stripe_customer_id on a non-entitled user = paid-but-stranded.
        # They get "activating / refresh", never a pay-again CTA.
        self.p1.stripe_customer_id = "cus_stranded"
        self.p1.save(update_fields=["stripe_customer_id"])
        self.client.force_login(self.p1)
        with mock.patch(_SCOUT_FN) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_not_called()
        self.assertContains(r, "Refresh my plan")
        self.assertContains(r, "activating")
        self.assertNotContains(r, "Upgrade to PRO")

    def test_pro_user_sparse_history_shows_empty_state(self):
        self._make_pro(self.p1)
        self.client.force_login(self.p1)
        with mock.patch(_SCOUT_FN, return_value={"reason": "insufficient_history", "settled_picks": 2}):
            r = self.client.get(self.url)
        self.assertContains(r, "Not enough betting history yet")


@override_settings(STRIPE_SECRET_KEY="")
class PublicAcceptScoutTests(TestCase):
    """Scout the creator before joining a public match."""

    def setUp(self):
        self.creator = make_user("creator")
        self.joiner = make_user("joiner")
        self.match = Match.objects.create(
            player_1=self.creator, match_type="public", match_state="created",
        )
        self.url = reverse("core-portal:portal-public-match-detail", args=[self.match.id])

    def test_pro_joiner_sees_scout_card(self):
        _make_pro(self.joiner)
        self.client.force_login(self.joiner)
        with mock.patch(_SCOUT_FN, return_value=_SCOUT) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_called_once_with(self.creator)
        self.assertContains(r, f"Scouting {self.creator.username}")

    def test_free_joiner_sees_upsell_and_paywall(self):
        self.client.force_login(self.joiner)
        r = self.client.get(self.url)
        self.assertContains(r, "Upgrade to PRO")
        evt = ProductEvent.objects.filter(name="paywall_viewed").first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.props.get("context"), "public_accept")


@override_settings(USE_AGGRIGATOR=False, STRIPE_SECRET_KEY="")
class DuelChallengeScoutTests(TestCase):
    """Scout the challenger on an incoming duel before accepting."""

    def setUp(self):
        from core.match import duels
        from core.match.tests.factories import make_event, make_league, make_two_way_market
        self.challenger = make_user("challenger")
        self.viewer = make_user("viewer")
        self.challenger.add_friend(self.viewer)
        league = make_league()
        event = make_event(league)
        _, home, _ = make_two_way_market(event)
        duels.send_duel(self.challenger, self.viewer, event.id, home.id)
        self.url = reverse("core-portal:portal-duels")

    def test_pro_sees_per_challenge_scout(self):
        _make_pro(self.viewer)
        self.client.force_login(self.viewer)
        with mock.patch(_SCOUT_FN, return_value=_SCOUT) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_called_once_with(self.challenger)
        self.assertContains(r, f"Scouting {self.challenger.username}")

    def test_free_sees_single_upsell_and_paywall(self):
        self.client.force_login(self.viewer)
        with mock.patch(_SCOUT_FN) as m:
            r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        m.assert_not_called()
        self.assertContains(r, "Scout your challengers")
        self.assertEqual(
            ProductEvent.objects.filter(name="paywall_viewed", props__context="duel_challenge").count(),
            1,
        )


@override_settings(STRIPE_SECRET_KEY="")
class UpgradeClickTrackingTests(TestCase):
    def test_src_param_emits_paywall_upgrade_clicked(self):
        user = make_user("clicker")
        self.client.force_login(user)
        r = self.client.get(reverse("core-portal:billing-upgrade") + "?src=opponent_scouting")
        self.assertEqual(r.status_code, 200)
        evt = ProductEvent.objects.filter(name="paywall_upgrade_clicked").first()
        self.assertIsNotNone(evt)
        self.assertEqual(evt.props.get("feature"), "opponent_scouting")
