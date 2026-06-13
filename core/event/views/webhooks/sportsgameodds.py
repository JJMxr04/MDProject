"""Inbound webhook handler at ``/sportgameodds/webhook``.

Receives state updates from the new aggregator service (plan §4). Verifies the
HMAC-SHA256 signature, dedupes by ``idempotency_key``, upserts Event +
Markets + Selections from the schema-v1 envelope, and triggers the existing
match-completion / game-reopen hooks the aggregator's lifecycle decisions
imply.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from dateutil import parser as date_parser
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.event.models import (
    Event,
    League,
    Market,
    Selection,
    Sport,
    Team,
    WebhookReceived,
)

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1
SIGNATURE_HEADER = "HTTP_X_AGGRIGATOR_SIGNATURE"
MAX_SKEW_SECONDS = 300


class BadSignature(Exception):
    """Header malformed / stale / mismatched."""


class SportsGameOddsWebhookView(APIView):
    """Aggregator -> MDProject. HMAC-authenticated; idempotent per body."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = getattr(settings, "AGGRIGATOR_WEBHOOK_SECRET", "")
        if not secret:
            logger.error("AGGRIGATOR_WEBHOOK_SECRET not configured")
            return Response(status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            _verify_signature(request, secret)
        except BadSignature as exc:
            logger.warning("rejecting webhook: %s", exc)
            return Response(
                {"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            body: dict[str, Any] = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if body.get("schema_version") != SCHEMA_VERSION:
            return Response(
                {"detail": "schema mismatch"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        idempotency_key = body.get("idempotency_key")
        if not idempotency_key:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if WebhookReceived.objects.filter(idempotency_key=idempotency_key).exists():
            return Response(status=status.HTTP_409_CONFLICT)

        event_envelope = body.get("event") or {}
        markets_envelope = body.get("markets") or []
        event_name = body.get("event_name", "")

        # ---- 1) Persist Event + Markets + Selections (atomic) -------------
        # If this fails, return 500 so the sender retries. No audit row is
        # written — re-delivery will hit this branch again and either succeed
        # or hit the idempotency-dedupe gate above on a later attempt.
        try:
            event = self._apply(event_envelope, markets_envelope)
        except Exception:  # noqa: BLE001
            logger.exception(
                "webhook apply failed for event_id=%s",
                event_envelope.get("event_id"),
            )
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ---- 2) Audit row — record we accepted this delivery -------------
        # Done in its own try/except so a transient FK / unique race here
        # doesn't lose the receipt audit; logged loudly if it does fail.
        try:
            WebhookReceived.objects.create(
                event=event,
                idempotency_key=idempotency_key,
                event_name=event_name,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "WebhookReceived insert failed for event_id=%s key=%s",
                event.id, idempotency_key,
            )

        # ---- 3) Lifecycle propagation -------------------------------------
        # Each hook gets its own try/except — settlement propagation MUST NOT
        # fail the whole receipt (sender would retry and re-apply identical
        # data, which is wasted work). Failures here are visible in logs +
        # ``settle_pending_events`` nightly cron picks up anything missed.
        if event_name == "event.finalized":
            try:
                from core.event.odds.settlement import propagate_to_matches
                affected = propagate_to_matches(event)
                logger.info(
                    "webhook %s event=%s propagated to %d match(es)",
                    event_name, event.id, affected,
                )
            except Exception:  # noqa: BLE001
                logger.exception("propagate_to_matches failed for event=%s", event.id)
        elif event_name == "event.voided":
            try:
                from core.game.events import reopen_games_for_voided_event
                reopen_games_for_voided_event(event)
            except Exception:  # noqa: BLE001
                logger.exception("reopen_games_for_voided_event failed for event=%s", event.id)

        return Response(status=status.HTTP_200_OK)

    @transaction.atomic
    def _apply(self, ev: dict, markets: list[dict]) -> Event:
        league = League.objects.filter(id=ev.get("league_id")).first()
        sport = (
            (league.sport if league else None)
            or Sport.objects.filter(id=ev.get("sport_id")).first()
        )
        home_team = _upsert_team(ev.get("home_team"))
        away_team = _upsert_team(ev.get("away_team"))

        defaults = {
            "league": league,
            "sport": sport,
            "type": (ev.get("type") or "")[:16],
            "season_label": (ev.get("season_label") or "")[:64],
            "start_time": _parse_iso(ev.get("start_time")),
            "status_type": (ev.get("status_type") or "")[:32],
            "status_display": (ev.get("status_display") or "")[:64],
            "current_period_id": (ev.get("current_period_id") or "")[:16],
            "is_live": bool(ev.get("is_live")),
            "is_finalized": bool(ev.get("is_finalized")),
            "completed": bool(ev.get("completed")),
            "home_team": home_team,
            "away_team": away_team,
            "home_score": ev.get("home_score"),
            "away_score": ev.get("away_score"),
            "winner_code": ev.get("winner_code"),
            "feed_locked": bool(ev.get("feed_locked")),
        }
        # A failed Sport/League lookup (row not seeded locally) must not null
        # out a previously resolved value — Markets copy ``event.sport_id``
        # into a NOT NULL column.
        if sport is None:
            defaults.pop("sport")
        if league is None:
            defaults.pop("league")
        event, _ = Event.objects.update_or_create(
            id=ev["event_id"], defaults=defaults,
        )

        if markets and event.sport_id is None:
            logger.warning(
                "skipping %d market(s) for event=%s: no local Sport for "
                "sport_id=%s league_id=%s (seed via seed_sports_leagues)",
                len(markets), event.id, ev.get("sport_id"), ev.get("league_id"),
            )
            return event

        for m in markets:
            _upsert_market_with_selections(event, m)
        return event


# ---- helpers ---------------------------------------------------------------


def _verify_signature(request, secret: str) -> None:
    raw = request.META.get(SIGNATURE_HEADER) or request.headers.get(
        "X-Aggrigator-Signature", "",
    )
    if not raw:
        raise BadSignature("missing signature header")
    parts = {}
    for kv in raw.split(","):
        if "=" not in kv:
            raise BadSignature("malformed header")
        k, _, v = kv.strip().partition("=")
        parts[k] = v
    if "t" not in parts or "v1" not in parts:
        raise BadSignature("header missing t or v1")
    try:
        ts = int(parts["t"])
    except ValueError as exc:
        raise BadSignature("non-integer t") from exc
    if abs(int(time.time()) - ts) > MAX_SKEW_SECONDS:
        raise BadSignature("timestamp out of window")
    expected = hmac.new(
        secret.encode(),
        f"{ts}.".encode() + request.body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, parts["v1"]):
        raise BadSignature("signature mismatch")


def _upsert_team(team_envelope: dict | None) -> Team | None:
    if not team_envelope:
        return None
    team_id = team_envelope.get("team_id")
    league_id = team_envelope.get("league_id")
    if not team_id or not league_id:
        return None
    league = League.objects.filter(id=league_id).first()
    if league is None:
        return None
    pk = f"{league_id}:{team_id}"
    defaults = {
        "league": league,
        "team_id": team_id,
        "sport": league.sport,
        "name_long": (team_envelope.get("name_long") or team_id)[:128],
        "name_medium": (team_envelope.get("name_medium") or team_id)[:64],
        "name_short": (team_envelope.get("name_short") or team_id)[:32],
        "primary_color": team_envelope.get("primary_color"),
        "stat_entity_id": (team_envelope.get("stat_entity_id") or "")[:8],
    }
    # (league, team_id) is unique. A row can already hold that pair under a
    # DIFFERENT pk when the provider re-keys teams (SGO string IDs → real
    # odds-api.io IDs → simulator IDs all coexist in dev DBs). Match on the
    # natural key first and update in place — otherwise update_or_create
    # INSERTs a second row and the constraint 500s the whole webhook.
    existing = Team.objects.filter(league=league, team_id=team_id).first()
    if existing is not None and existing.id != pk:
        for field, value in defaults.items():
            setattr(existing, field, value)
        existing.save()
        return existing
    obj, _ = Team.objects.update_or_create(id=pk, defaults=defaults)
    return obj


def _upsert_market_with_selections(event: Event, m: dict) -> None:
    # ``Market.last_updated`` is NOT NULL — older aggregator payloads omitted
    # it. Fall back to ``now()`` so a missing field never blocks the webhook
    # apply (defense-in-depth; the aggregator should ship it).
    last_updated = _parse_iso(m.get("last_updated")) or timezone.now()
    defaults = {
        "event": event,
        "sport_id": event.sport_id,
        "category": m.get("category", ""),
        "type": (m.get("type") or "")[:64],
        "scope": m.get("scope", "FULL_GAME"),
        "line": _decimal(m.get("line")),
        "side": m.get("side", ""),
        "provider": "sportsgameodds",
        "provider_market_id": "",
        "provider_choice_group": "",
        "subject_team_id": m.get("subject_team_id"),
        "is_live": bool(m.get("is_live")),
        "suspended": bool(m.get("suspended")),
        "last_updated": last_updated,
    }
    market, _ = Market.objects.update_or_create(id=m["market_id"], defaults=defaults)

    for s in m.get("selections") or []:
        Selection.objects.update_or_create(
            id=s["selection_id"],
            defaults=dict(
                market=market,
                type=s.get("type", ""),
                label=(s.get("label") or "")[:128],
                decimal_odds=_decimal(s.get("decimal_odds")),
                opening_decimal_odds=_decimal(s.get("opening_decimal_odds")),
                movement=int(s.get("movement") or 0),
                settlement_status=s.get("settlement_status") or "PENDING",
                settled_at=_parse_iso(s.get("settled_at")),
                settlement_source=s.get("settlement_source") or "",
            ),
        )


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _parse_iso(value):
    if value in (None, ""):
        return None
    try:
        return date_parser.isoparse(value)
    except (ValueError, TypeError):
        return None
