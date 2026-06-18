"""Tests for the inbound aggregator webhook (``SportsGameOddsWebhookView``).

Focus: the Sport/League auto-provisioning that lets a newly-activated league
(e.g. VOLLEYBALL/VNL) land without a NULL ``Market.sport_id`` IntegrityError.
The aggregator only ever sends string IDs in the envelope, so the receiver
must materialize the catalog rows itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from django.test import TestCase, override_settings
from django.urls import reverse

from core.event.models import Event, League, Market, Selection, Sport

SECRET = "test-webhook-secret"


def _sign(body: bytes, *, ts: int | None = None) -> str:
    ts = ts if ts is not None else int(time.time())
    mac = hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def _vnl_envelope(*, event_id: str = "68882968") -> dict:
    """A men's VNL event as the aggregator emits it — bare ``sport_id`` /
    ``league_id`` strings, no nested name objects (see payload.py)."""
    return {
        "schema_version": 1,
        "event_name": "event.updated",
        "idempotency_key": f"key-{event_id}",
        "event": {
            "event_id": event_id,
            "sport_id": "VOLLEYBALL",
            "league_id": "VNL",
            "type": "match",
            "season_label": "2026",
            "start_time": "2026-06-13T18:00:00Z",
            "status_type": "notstarted",
            "status_display": "Scheduled",
            "is_live": False, "is_finalized": False, "completed": False,
            "feed_locked": False,
            "home_team": {
                "team_id": "USA", "league_id": "VNL",
                "name_long": "United States", "name_medium": "USA",
                "name_short": "USA", "primary_color": "#0A3161",
                "stat_entity_id": "home",
            },
            "away_team": {
                "team_id": "BRA", "league_id": "VNL",
                "name_long": "Brazil", "name_medium": "Brazil",
                "name_short": "BRA", "primary_color": "#009C3B",
                "stat_entity_id": "away",
            },
            "home_score": None, "away_score": None, "winner_code": None,
        },
        "markets": [
            {
                "market_id": f"{event_id}-ml-ft-points-home",
                "category": "MONEYLINE", "type": "VNL_POINTS_ML",
                "scope": "FULL_GAME", "line": None, "side": "HOME",
                "subject_team_id": "VNL:USA",
                "is_live": False, "suspended": False,
                "last_updated": "2026-06-13T01:10:10Z",
                "selections": [
                    {
                        "selection_id": f"{event_id}-ml-ft-points-home-usa",
                        "type": "HOME", "label": "United States",
                        "decimal_odds": "1.5000",
                        "opening_decimal_odds": "1.5500",
                        "movement": -1,
                        "settlement_status": "PENDING",
                        "settlement_source": "",
                        "settled_at": None,
                    },
                ],
            },
        ],
    }


@override_settings(AGGRIGATOR_WEBHOOK_SECRET=SECRET)
class WebhookProvisioningTests(TestCase):
    url = None

    def setUp(self):
        self.url = reverse("sportgameodds-webhook")

    def _post(self, envelope: dict, *, ts: int | None = None):
        body = json.dumps(envelope).encode()
        return self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_AGGRIGATOR_SIGNATURE=_sign(body, ts=ts),
        )

    def test_unknown_sport_and_league_are_provisioned(self):
        """A VNL event for a sport MDProject has never seen creates the
        Sport + League rows and persists the market with a non-null sport."""
        self.assertFalse(Sport.objects.filter(id="VOLLEYBALL").exists())

        resp = self._post(_vnl_envelope())
        self.assertEqual(resp.status_code, 200)

        sport = Sport.objects.get(id="VOLLEYBALL")
        self.assertEqual(sport.name, "Volleyball")
        # Created INACTIVE — must not enter MDProject's local SGO ingest cron.
        self.assertFalse(sport.active)

        league = League.objects.get(id="VNL")
        self.assertEqual(league.sport_id, "VOLLEYBALL")
        self.assertFalse(league.active)

        event = Event.objects.get(id="68882968")
        self.assertEqual(event.sport_id, "VOLLEYBALL")
        self.assertEqual(event.league_id, "VNL")

        market = Market.objects.get(id="68882968-ml-ft-points-home")
        self.assertEqual(market.sport_id, "VOLLEYBALL")
        self.assertEqual(market.type, "VNL_POINTS_ML")
        self.assertEqual(Selection.objects.filter(market=market).count(), 1)

    def test_second_event_reuses_existing_rows(self):
        """A later VNL event doesn't duplicate the catalog rows."""
        self.assertEqual(self._post(_vnl_envelope(event_id="68882964")).status_code, 200)
        self.assertEqual(self._post(_vnl_envelope(event_id="68882968")).status_code, 200)

        self.assertEqual(Sport.objects.filter(id="VOLLEYBALL").count(), 1)
        self.assertEqual(League.objects.filter(id="VNL").count(), 1)
        self.assertEqual(Event.objects.filter(league_id="VNL").count(), 2)

    def test_missing_sport_id_skips_markets_without_500(self):
        """Pathological envelope with no sport_id: event still records, but
        markets are skipped rather than raising an IntegrityError."""
        env = _vnl_envelope(event_id="70000001")
        env["event"]["sport_id"] = None
        env["event"]["league_id"] = None
        # teams reference league VNL which now won't exist -> dropped too.
        env["event"]["home_team"]["league_id"] = None
        env["event"]["away_team"]["league_id"] = None

        resp = self._post(env)
        self.assertEqual(resp.status_code, 200)

        event = Event.objects.get(id="70000001")
        self.assertIsNone(event.sport_id)
        self.assertEqual(Market.objects.filter(event=event).count(), 0)

    def test_existing_event_sport_not_clobbered_by_null(self):
        """Once an event has a resolved sport, a later envelope that fails
        resolution must not null it back out (markets keep their FK)."""
        self.assertEqual(self._post(_vnl_envelope(event_id="68882968")).status_code, 200)
        self.assertEqual(Event.objects.get(id="68882968").sport_id, "VOLLEYBALL")

        env = _vnl_envelope(event_id="68882968")
        env["event"]["sport_id"] = None
        env["event"]["league_id"] = None
        env["idempotency_key"] = "key-68882968-again"
        self.assertEqual(self._post(env).status_code, 200)

        self.assertEqual(Event.objects.get(id="68882968").sport_id, "VOLLEYBALL")


@override_settings(AGGRIGATOR_WEBHOOK_SECRET=SECRET)
class WebhookTeamColorsTests(TestCase):
    def setUp(self):
        self.url = reverse("sportgameodds-webhook")

    def _post(self, envelope: dict, *, ts: int | None = None):
        body = json.dumps(envelope).encode()
        return self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_AGGRIGATOR_SIGNATURE=_sign(body, ts=ts),
        )

    def test_team_stores_all_four_colors(self):
        from core.event.models import Team

        env = _vnl_envelope(event_id="69000001")
        env["event"]["home_team"].update({
            "primary_color": "#0A3161",
            "secondary_color": "#B31942",
            "primary_contrast": "#FFFFFF",
            "secondary_contrast": "#000000",
        })

        self.assertEqual(self._post(env).status_code, 200)

        team = Team.objects.get(id="VNL:USA")
        self.assertEqual(team.primary_color, "#0A3161")
        self.assertEqual(team.secondary_color, "#B31942")
        self.assertEqual(team.primary_contrast, "#FFFFFF")
        self.assertEqual(team.secondary_contrast, "#000000")
