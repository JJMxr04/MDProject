"""Event — one match. PK is the SGO ``eventID`` string.

Status type is derived from SGO's status booleans. Settlement and game-reopen
hooks fire at the same lifecycle transitions as before — only the upstream
shape changed.
"""

import logging
import uuid

from django.db import models

from core.event.models.league import League
from core.event.models.sport import Sport
from core.event.models.team import Team

logger = logging.getLogger(__name__)


def _winner_name(winner_code, home, away):
    if winner_code == 1 and home:
        return home.name_long
    if winner_code == 2 and away:
        return away.name_long
    if winner_code == 3:
        return "Draw"
    return None


def _should_settle(previous, obj) -> bool:
    """First-finish trigger or score correction on an already-finished event."""
    if obj.status_type != "finished":
        return False
    if previous is None:
        return True
    if previous.status_type != "finished":
        return True
    return (
        previous.home_score != obj.home_score
        or previous.away_score != obj.away_score
    )


def _should_reopen(previous, obj) -> bool:
    """First-time void trigger."""
    if obj.status_type not in ("postponed", "canceled"):
        return False
    if previous is None:
        return True
    return previous.status_type != obj.status_type


class EventManager(models.Manager):
    def get_by_public_id(self, public_id):
        return self.filter(public_id=public_id).first()

    def active(self):
        return self.filter(status_type__in=["notstarted", "inprogress"])

    def upsert_from_spec(self, spec, *, home: Team | None, away: Team | None) -> "Event":
        """Create or update from a ``core.event.odds.sgo_normalize.EventSpec``.

        ``home`` / ``away`` should be the upserted ``Team`` rows resolved from
        the spec's ``home_team`` / ``away_team``. We don't re-resolve them
        here so the caller can batch.
        """
        league = League.objects.filter(id=spec.league_id).first()
        sport = (league.sport if league else None) or Sport.objects.filter(id=spec.sport_id).first()

        defaults = {
            "league": league,
            "sport": sport,
            "type": (spec.type or "")[:16],
            "season_label": (spec.season_label or "")[:64],
            "start_time": spec.start_time,
            "status_type": (spec.status_type or "")[:32],
            "status_display": (spec.status_display or "")[:64],
            "current_period_id": (spec.current_period_id or "")[:16],
            "is_live": bool(spec.is_live),
            "is_finalized": bool(spec.is_finalized),
            "completed": bool(spec.completed),
            "home_team": home,
            "away_team": away,
            "home_score": spec.home_score,
            "away_score": spec.away_score,
            "winner_code": spec.winner_code,
            "winner": _winner_name(spec.winner_code, home, away),
            "feed_locked": bool(spec.feed_locked),
        }

        previous = self.filter(id=spec.event_id).only(
            "status_type", "home_score", "away_score"
        ).first()
        obj, _ = self.update_or_create(id=spec.event_id, defaults=defaults)

        if _should_settle(previous, obj):
            from core.event.odds.settlement import settle_event
            try:
                settle_event(obj)
            except Exception:  # noqa: BLE001 — settlement must not break ingest
                logger.exception("settle_event failed for event=%s", obj.id)
        if _should_reopen(previous, obj):
            from core.game.events import reopen_games_for_voided_event
            try:
                reopen_games_for_voided_event(obj)
            except Exception:  # noqa: BLE001 — never break ingest
                logger.exception(
                    "reopen_games_for_voided_event failed for event=%s", obj.id
                )
        return obj


class Event(models.Model):
    id = models.CharField(max_length=32, primary_key=True)
    public_id = models.UUIDField(
        db_index=True, unique=True, default=uuid.uuid4, editable=False
    )

    sport = models.ForeignKey(
        Sport, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    league = models.ForeignKey(
        League, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )
    type = models.CharField(max_length=16, blank=True)
    season_label = models.CharField(max_length=64, blank=True)

    start_time = models.DateTimeField(null=True, blank=True, db_index=True)

    status_type = models.CharField(max_length=32, db_index=True, blank=True)
    status_display = models.CharField(max_length=64, blank=True)
    current_period_id = models.CharField(max_length=16, blank=True)
    is_live = models.BooleanField(default=False, db_index=True)
    is_finalized = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)

    home_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="home_events"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="away_events"
    )

    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)

    winner_code = models.SmallIntegerField(null=True, blank=True)
    winner = models.CharField(max_length=255, null=True, blank=True)

    feed_locked = models.BooleanField(default=False)
    last_provider_refresh_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = EventManager()

    class Meta:
        db_table = "core_event_event"
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["league", "status_type", "start_time"]),
            models.Index(fields=["sport", "status_type", "start_time"]),
        ]

    def __str__(self):
        home = self.home_team.name_long if self.home_team else "?"
        away = self.away_team.name_long if self.away_team else "?"
        return f"{home} vs {away}"
