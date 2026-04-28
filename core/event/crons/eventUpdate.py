"""Event ingest from SportsGameOdds.

One ``GET /events?leagueID={...}&startsAfter=…&startsBefore=…`` call per
active league per tick. Each call returns events with embedded teams, status,
results, and odds — all of which land in the DB in a single transaction.

Per-league cadence is data-driven: each ``League`` row carries a
``refresh_cadence_minutes`` and ``last_refreshed_at``. The outer beat ticks
every couple of hours; this cron checks each active league and skips any that
isn't yet due.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.event.models import Event, League, Team
from core.event.odds.sgo_normalize import EventSpec, event_spec_from_payload
from core.event.providers import (
    QuotaExceeded,
    SportsGameOddsError,
    get_events_client,
)

logger = logging.getLogger(__name__)


# How far ahead and behind the current moment we ask SGO for events.
LOOKBACK = timedelta(hours=2)
LOOKAHEAD = timedelta(hours=72)
LIVE_LOOKAHEAD = timedelta(hours=12)


class EventCron:
    """Per-league event ingest. The orchestration here decides which leagues
    are due; the heavy lifting lives in ``ingest_league`` + the normalizer."""

    def __init__(self, client=None):
        self.client = client or get_events_client()

    # ------------------------------------------------------------------ outer

    def update_due_leagues(self) -> dict:
        """Walk every active League and ingest if cadence has elapsed."""
        report = {"considered": 0, "ingested": {}, "skipped_not_due": [], "errors": []}
        now = timezone.now()
        for league in League.objects.filter(active=True).select_related("sport"):
            report["considered"] += 1
            if not League.objects.is_due(league, now=now):
                report["skipped_not_due"].append(league.id)
                continue
            try:
                count = self.ingest_league(league)
            except QuotaExceeded as exc:
                logger.warning("Skipping %s: %s", league.id, exc)
                report["errors"].append((league.id, "quota"))
                break
            except SportsGameOddsError as exc:
                logger.warning("SGO error on %s: %s", league.id, exc)
                report["errors"].append((league.id, str(exc)))
                continue
            report["ingested"][league.id] = count
        logger.info("EventCron.update_due_leagues report: %s", report)
        return report

    # ------------------------------------------------------------------ inner

    def ingest_league(self, league: League) -> int:
        """Pull events for one league across the lookahead window and upsert."""
        now = timezone.now()
        starts_after = now - LOOKBACK
        starts_before = now + LOOKAHEAD
        ingested = 0
        for raw in self.client.get_events(
            league_id=league.id,
            starts_after=_iso(starts_after),
            starts_before=_iso(starts_before),
            include_open_close=True,
            odds_available=None,
            limit=50,
        ):
            spec = event_spec_from_payload(raw)
            if spec is None:
                continue
            try:
                self._persist(spec, raw, league)
            except Exception:  # noqa: BLE001 — keep walking, log once per event
                logger.exception("ingest failed for event=%s", spec.event_id)
                continue
            ingested += 1
        league.last_refreshed_at = timezone.now()
        league.save(update_fields=["last_refreshed_at"])
        logger.info("ingest_league %s: %d events", league.id, ingested)
        return ingested

    def ingest_live(self) -> int:
        """Live-only sweep — much smaller payloads, used for in-play refresh."""
        ingested = 0
        for league in League.objects.filter(active=True):
            for raw in self.client.get_events(
                league_id=league.id,
                live=True,
                odds_available=True,
                limit=50,
            ):
                spec = event_spec_from_payload(raw)
                if spec is None:
                    continue
                try:
                    self._persist(spec, raw, league)
                except Exception:  # noqa: BLE001
                    logger.exception("live ingest failed for event=%s", spec.event_id)
                    continue
                ingested += 1
        return ingested

    # ------------------------------------------------------------------ persist

    @transaction.atomic
    def _persist(self, spec: EventSpec, raw: dict, league: League) -> Event:
        """Write one EventSpec + its team and odds rows. Atomic per event."""
        home = Team.objects.upsert_from_spec(spec.home_team)
        away = Team.objects.upsert_from_spec(spec.away_team)
        event = Event.objects.upsert_from_spec(spec, home=home, away=away)

        # Update last-refresh timestamp regardless of odds presence.
        Event.objects.filter(pk=event.pk).update(last_provider_refresh_at=timezone.now())

        # Upsert markets / selections from the spec's already-built market list.
        from core.event.odds.sgo_ingest import write_markets

        write_markets(event, spec.markets)
        return event


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# Backwards-compatible top-level entry — Celery tasks import this name.
def update_all_events():
    EventCron().update_due_leagues()
