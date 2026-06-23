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
    POTD_TZ,
    DailyPick,
    DailyPickResult,
    PickError,
    PickOfDay,
    potd_today,
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


def listing_item(event_id, *, league_id="NHL", start, priced=True,
                 types=("HOME", "AWAY")):
    return {
        "id": event_id,
        "league": {"id": league_id},
        "start_time": start.isoformat(),
        "markets": [{
            "category": "MONEYLINE",
            "scope": "FULL_GAME",
            "selections": [
                {
                    "id": f"{event_id}:{t.lower()}",
                    "type": t,
                    "decimal_odds": "1.90" if priced else None,
                }
                for t in types
            ],
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
        event_id, market, _ = pick_candidate(items, date=self.date)
        self.assertEqual(event_id, "prime")
        self.assertEqual(
            [s["id"] for s in market["selections"]],
            ["prime:home", "prime:away"],
        )

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

    def test_three_way_market_keeps_draw_selection(self):
        items = [listing_item(
            "soccer", start=self.prime, types=("HOME", "DRAW", "AWAY"),
        )]
        _, market, _ = pick_candidate(items, date=self.date)
        self.assertEqual(
            [s["type"] for s in market["selections"]],
            ["HOME", "DRAW", "AWAY"],
        )

    def test_empty_slate_returns_none(self):
        self.assertIsNone(pick_candidate([], date=self.date))


class CurateServiceTests(TestCase):
    def _curate(self, items, chain_side_effect):
        client = MagicMock()
        client.list_events.return_value = {"items": items}
        with patch(
            "core.event.providers.aggregator_client.AggrigatorClient",
            return_value=client,
        ), patch(
            "core.event.services.aggregator_chain.ensure_chain",
            side_effect=chain_side_effect,
        ) as chain:
            potd = curate_pick_of_day()
        return potd, chain

    def test_creates_row_and_mirrors_every_selection(self):
        league = make_league("CUR")
        event = make_event(league, start_time=timezone.now() + timedelta(hours=8))
        market, home, away = make_two_way_market(event)
        items = [listing_item(event.id, start=event.start_time)]
        # ensure_chain returns the matching local selection per call.
        chain_map = {f"{event.id}:home": home, f"{event.id}:away": away}

        with patch("core.potd.services._schedule_closing_nudge") as nudge:
            potd, chain = self._curate(
                items, lambda eid, sid: chain_map[sid],
            )
        self.assertEqual(potd.date, potd_today())
        self.assertEqual(potd.event_id, event.id)
        self.assertEqual(potd.market_id, market.id)
        self.assertEqual(potd.lock_time, event.start_time)
        # Every priced selection mirrored — both sides pickable on the card.
        self.assertEqual(chain.call_count, 2)
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


class DashboardCardTests(TestCase):
    def test_card_offers_every_selection_humanized(self):
        """Regression: the card only rendered the single mirrored seed
        selection ("home home") — every side must be a button, with
        team-name labels."""
        from core.potd.views import potd_card_context

        user = make_user("card")
        potd, home, away = make_potd()
        ctx = potd_card_context(user)

        labels = [o["label"] for o in ctx["potd_options"]]
        self.assertEqual(len(labels), 2)
        # humanize_selection renders "<team long name> to win"
        self.assertTrue(any("to win" in l for l in labels), labels)
        self.assertNotIn("home", [l.lower() for l in labels])
        # HOME sorts before AWAY.
        self.assertEqual(ctx["potd_options"][0]["id"], home.id)


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


class AdminPicksVisibilityTests(TestCase):
    def test_potd_admin_page_lists_picks(self):
        """The PickOfDay admin change page shows everyone's picks inline."""
        admin_user = make_user("admin")
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        potd, home, _ = make_potd()
        picker = make_user("crowd")
        DailyPick.objects.create(user=picker, potd=potd, selection=home)

        self.client.force_login(admin_user)
        url = reverse("admin:core_potd_pickofday_change", args=[potd.pk])
        resp = self.client.get(url, secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, picker.username)


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


class CurateCronScheduleTests(TestCase):
    """The curate cron must fire just *after* the NY product-day starts.

    Procrastinate evaluates @app.periodic cron strings in UTC (croniter over
    epoch floats — no tz support), while curation derives its target day from
    ``potd_today()`` = the America/New_York date. A naive ``10 0 * * *`` fires
    at 00:10 UTC = ~8pm NY the *prior* evening, so it curates yesterday and the
    actual NY day has no pick for ~20h (the "card shows countdown forever" bug).
    The cron must land in the early morning of the day it curates, in BOTH DST
    regimes.
    """

    def test_curate_cron_fires_early_in_target_ny_day(self):
        import croniter
        from zoneinfo import ZoneInfo

        from procrastinate.contrib.django import app

        import core.potd.tasks  # noqa: F401 — ensure periodic registration

        cron = app.periodic_registry.periodic_tasks[
            ("core.potd.curate_pick_of_day", "")
        ].cron

        for day in ("2026-06-15", "2026-01-15"):  # EDT (summer) and EST (winter)
            y, m, d = (int(p) for p in day.split("-"))
            base = datetime(y, m, d, 12, tzinfo=ZoneInfo("UTC")).timestamp()
            fire_ts = croniter.croniter(cron).get_next(float, start_time=base)
            fire_ny = datetime.fromtimestamp(fire_ts, POTD_TZ)
            self.assertLess(
                fire_ny.hour, 6,
                msg=(
                    f"curate cron {cron!r} fires at NY {fire_ny:%Y-%m-%d %H:%M %Z}; "
                    "it must fire in the early morning of the product-day it "
                    "curates, not the prior evening"
                ),
            )
