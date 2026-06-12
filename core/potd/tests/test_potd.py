"""Pick of the Day (plan Phase 6): curation, picking, streaks, results,
leaderboard, nudge targeting."""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.match.tests.factories import (
    make_event,
    make_league,
    make_two_way_market,
    make_user,
    settle_selection,
)
from core.metrics.models import ProductEvent
from core.potd.models import (
    POTD_TZ, DailyPick, DailyPickResult, PickError, PickOfDay, potd_today,
)
from core.potd.services import CurationError, curate_pick_of_day, pick_candidate


def make_potd(*, date=None, lock_in=timedelta(hours=6)):
    """A PickOfDay over a locally built event + 2-way moneyline market."""
    league = make_league("POTD")
    event = make_event(league, start_time=timezone.now() + lock_in)
    market, home, away = make_two_way_market(event)
    potd = PickOfDay.objects.create(
        date=date or potd_today(),
        event=event,
        market=market,
        lock_time=event.start_time,
    )
    return potd, home, away


def listing_item(event_id, *, league_id="NHL", start, priced=True):
    return {
        "id": event_id,
        "league": {"id": league_id},
        "start_time": start.isoformat(),
        "markets": [{
            "category": "MONEYLINE",
            "scope": "FULL_GAME",
            "selections": [{
                "id": f"{event_id}:home",
                "type": "HOME",
                "decimal_odds": "1.90" if priced else None,
            }],
        }],
    }


class CurationHeuristicTests(TestCase):
    def setUp(self):
        self.date = potd_today() + timedelta(days=1)
        self.prime = datetime.combine(
            self.date, time(hour=19), tzinfo=POTD_TZ,
        )

    def test_prefers_kickoff_closest_to_prime_time(self):
        items = [
            listing_item("noon", start=self.prime - timedelta(hours=7)),
            listing_item("prime", start=self.prime + timedelta(minutes=10)),
            listing_item("late", start=self.prime + timedelta(hours=4)),
        ]
        event_id, selection_id, _ = pick_candidate(items, date=self.date)
        self.assertEqual(event_id, "prime")
        self.assertEqual(selection_id, "prime:home")

    def test_featured_league_outranks_prime_time(self):
        items = [
            listing_item("prime-minor", league_id="MINOR", start=self.prime),
            listing_item("late-epl", league_id="EPL",
                         start=self.prime + timedelta(hours=3)),
        ]
        with self.settings(POTD_FEATURED_LEAGUES=["EPL", "NHL"]):
            event_id, _, _ = pick_candidate(items, date=self.date)
        self.assertEqual(event_id, "late-epl")

    def test_skips_events_without_priced_moneyline(self):
        items = [
            listing_item("unpriced", start=self.prime, priced=False),
            listing_item("priced", start=self.prime + timedelta(hours=2)),
        ]
        event_id, _, _ = pick_candidate(items, date=self.date)
        self.assertEqual(event_id, "priced")

    def test_empty_slate_returns_none(self):
        self.assertIsNone(pick_candidate([], date=self.date))


class CurateServiceTests(TestCase):
    def _curate(self, items, local_selection):
        client = MagicMock()
        client.list_events.return_value = {"items": items}
        with patch(
            "core.event.providers.aggregator_client.AggrigatorClient",
            return_value=client,
        ), patch(
            "core.event.services.aggregator_chain.ensure_chain",
            return_value=local_selection,
        ):
            return curate_pick_of_day()

    def test_creates_row_and_is_idempotent(self):
        league = make_league("CUR")
        event = make_event(league, start_time=timezone.now() + timedelta(hours=8))
        market, home, _ = make_two_way_market(event)
        items = [listing_item(event.id, start=event.start_time)]

        with patch("core.potd.services._schedule_closing_nudge") as nudge:
            potd = self._curate(items, home)
        self.assertEqual(potd.date, potd_today())
        self.assertEqual(potd.event_id, event.id)
        self.assertEqual(potd.market_id, market.id)
        self.assertEqual(potd.lock_time, event.start_time)
        nudge.assert_called_once_with(potd)

        # Second run returns the same row without touching the catalog.
        again = curate_pick_of_day()
        self.assertEqual(again.pk, potd.pk)
        self.assertEqual(PickOfDay.objects.count(), 1)

    def test_admin_precurated_day_is_left_alone(self):
        potd, _, _ = make_potd()
        PickOfDay.objects.filter(pk=potd.pk).update(manually_curated=True)
        result = curate_pick_of_day()
        self.assertEqual(result.pk, potd.pk)

    def test_empty_slate_raises_curation_error(self):
        client = MagicMock()
        client.list_events.return_value = {"items": []}
        with patch(
            "core.event.providers.aggregator_client.AggrigatorClient",
            return_value=client,
        ):
            with self.assertRaises(CurationError):
                curate_pick_of_day()
        self.assertEqual(PickOfDay.objects.count(), 0)


class RecordPickTests(TestCase):
    def setUp(self):
        self.user = make_user("picker")
        self.potd, self.home, self.away = make_potd()

    def test_pick_creates_row_and_starts_streak(self):
        pick = DailyPick.objects.record_pick(
            user=self.user, potd=self.potd, selection=self.home,
        )
        self.assertEqual(pick.result, DailyPickResult.PENDING)
        self.user.refresh_from_db()
        self.assertEqual(self.user.potd_current_streak, 1)
        self.assertEqual(self.user.potd_best_streak, 1)
        self.assertEqual(self.user.potd_last_pick_date, self.potd.date)
        event = ProductEvent.objects.filter(name="potd_picked", user=self.user).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.props["streak"], 1)

    def test_picking_twice_same_day_is_impossible(self):
        DailyPick.objects.record_pick(
            user=self.user, potd=self.potd, selection=self.home,
        )
        with self.assertRaises(PickError):
            DailyPick.objects.record_pick(
                user=self.user, potd=self.potd, selection=self.away,
            )
        self.assertEqual(DailyPick.objects.filter(user=self.user).count(), 1)

    def test_locked_potd_rejects_pick(self):
        PickOfDay.objects.filter(pk=self.potd.pk).update(
            lock_time=timezone.now() - timedelta(minutes=1),
        )
        self.potd.refresh_from_db()
        with self.assertRaises(PickError):
            DailyPick.objects.record_pick(
                user=self.user, potd=self.potd, selection=self.home,
            )

    def test_selection_outside_market_rejected(self):
        league = make_league("OTHER")
        other_event = make_event(league)
        _, stray, _ = make_two_way_market(other_event)
        with self.assertRaises(PickError):
            DailyPick.objects.record_pick(
                user=self.user, potd=self.potd, selection=stray,
            )


class StreakBoundaryTests(TestCase):
    """Streak extends/resets across a settled day boundary."""

    def test_consecutive_day_extends_after_yesterday_settles(self):
        user = make_user("streaker")
        yesterday = potd_today() - timedelta(days=1)
        y_potd, y_home, y_away = make_potd(date=yesterday)
        y_pick = DailyPick.objects.create(user=user, potd=y_potd, selection=y_home)
        user.potd_current_streak = 1
        user.potd_best_streak = 3
        user.potd_last_pick_date = yesterday
        user.save()

        # Simulated settle: yesterday's selection wins, results sync.
        settle_selection(y_home, "WON")
        settle_selection(y_away, "LOST")
        DailyPick.objects.sync_pending()
        y_pick.refresh_from_db()
        self.assertEqual(y_pick.result, DailyPickResult.WON)

        # Today's pick extends the streak across the boundary.
        t_potd, t_home, _ = make_potd()
        DailyPick.objects.record_pick(user=user, potd=t_potd, selection=t_home)
        user.refresh_from_db()
        self.assertEqual(user.potd_current_streak, 2)
        self.assertEqual(user.potd_best_streak, 3)  # best untouched until beaten

    def test_gap_resets_streak(self):
        user = make_user("lapsed")
        user.potd_current_streak = 9
        user.potd_best_streak = 9
        user.potd_last_pick_date = potd_today() - timedelta(days=3)
        user.save()

        potd, home, _ = make_potd()
        DailyPick.objects.record_pick(user=user, potd=potd, selection=home)
        user.refresh_from_db()
        self.assertEqual(user.potd_current_streak, 1)
        self.assertEqual(user.potd_best_streak, 9)


class ResultSyncTests(TestCase):
    def test_sync_maps_settlement_statuses(self):
        potd, home, away = make_potd()
        winner = DailyPick.objects.create(
            user=make_user("w"), potd=potd, selection=home,
        )
        loser = DailyPick.objects.create(
            user=make_user("l"), potd=potd, selection=away,
        )
        settle_selection(home, "WON")
        settle_selection(away, "LOST")

        changed = DailyPick.objects.sync_pending()
        self.assertEqual(changed, 2)
        winner.refresh_from_db()
        loser.refresh_from_db()
        self.assertEqual(winner.result, DailyPickResult.WON)
        self.assertEqual(loser.result, DailyPickResult.LOST)

    def test_void_and_push_map_to_void(self):
        potd, home, away = make_potd()
        voided = DailyPick.objects.create(
            user=make_user("v"), potd=potd, selection=home,
        )
        settle_selection(home, "VOID")
        DailyPick.objects.sync_pending()
        voided.refresh_from_db()
        self.assertEqual(voided.result, DailyPickResult.VOID)


class PickEndpointTests(TestCase):
    def setUp(self):
        self.user = make_user("web")
        self.potd, self.home, self.away = make_potd()
        self.url = reverse("core-portal:potd-pick")
        self.client.force_login(self.user)

    def _post(self, selection_id):
        return self.client.post(
            self.url,
            json.dumps({"selection_id": selection_id}),
            content_type="application/json",
            secure=True,
        )

    def test_one_tap_pick_succeeds(self):
        resp = self._post(self.home.id)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["streak"], 1)
        self.assertTrue(
            DailyPick.objects.filter(user=self.user, potd=self.potd).exists()
        )

    def test_double_pick_rejected(self):
        self._post(self.home.id)
        resp = self._post(self.away.id)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already", resp.json()["message"])

    def test_unknown_selection_rejected(self):
        resp = self._post("not-a-selection")
        self.assertEqual(resp.status_code, 400)


class LeaderboardViewTests(TestCase):
    def test_renders_boards_and_syncs_results(self):
        potd, home, away = make_potd()
        winner = make_user("board_w")
        DailyPick.objects.create(user=winner, potd=potd, selection=home)
        winner.potd_current_streak = 4
        winner.potd_best_streak = 6
        winner.save()
        settle_selection(home, "WON")

        self.client.force_login(make_user("viewer"))
        resp = self.client.get(
            reverse("core-portal:potd-leaderboard"), secure=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, winner.username)
        self.assertContains(resp, "🔥 4")
        # Lazy sync ran during render.
        self.assertEqual(
            DailyPick.objects.get(user=winner).result, DailyPickResult.WON,
        )


class ClosingNudgeTests(TestCase):
    def test_targets_only_at_risk_streaks(self):
        from core.mail.models import Notification
        from core.potd.services import send_closing_nudge

        potd, home, _ = make_potd()
        yesterday = potd.date - timedelta(days=1)

        at_risk = make_user("at_risk")
        at_risk.potd_last_pick_date = yesterday
        at_risk.save()

        already_picked = make_user("picked")
        already_picked.potd_last_pick_date = yesterday
        already_picked.save()
        DailyPick.objects.create(user=already_picked, potd=potd, selection=home)

        lapsed = make_user("not_at_risk")  # no streak to protect
        lapsed.potd_last_pick_date = yesterday - timedelta(days=5)
        lapsed.save()

        sent = send_closing_nudge(str(potd.pk))
        self.assertEqual(sent, 1)
        self.assertTrue(
            Notification.objects.filter(
                user=at_risk, message__icontains="closes in 2 hours",
            ).exists()
        )
        self.assertFalse(Notification.objects.filter(user=already_picked).exists())
        self.assertFalse(Notification.objects.filter(user=lapsed).exists())

    def test_locked_potd_sends_nothing(self):
        from core.potd.services import send_closing_nudge

        potd, _, _ = make_potd()
        PickOfDay.objects.filter(pk=potd.pk).update(
            lock_time=timezone.now() - timedelta(minutes=5),
        )
        user = make_user("late")
        user.potd_last_pick_date = potd.date - timedelta(days=1)
        user.save()

        self.assertEqual(send_closing_nudge(str(potd.pk)), 0)
