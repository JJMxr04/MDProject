import uuid
from datetime import datetime, timezone

from django.db import models

from core.event.models.sport import Sport
from core.event.models.team import Team


def _utc_from_ts(ts):
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _winner_name(winner_code, home, away):
    if winner_code == 1 and home:
        return home.name
    if winner_code == 2 and away:
        return away.name
    if winner_code == 3:
        return "Draw"
    return None


def _should_settle(previous, obj) -> bool:
    """Trigger settlement when we first see a finished status, or when the
    final scores get corrected on an already-finished event."""
    if obj.status_type != "finished":
        return False
    if previous is None:
        return True
    if previous.status_type != "finished":
        return True
    return (
        previous.home_score != obj.home_score or previous.away_score != obj.away_score
    )


def _should_reopen(previous, obj) -> bool:
    """Trigger game reopen when an event first transitions to a void state."""
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

    def upsert_from_payload(self, payload, sport=None, home=None, away=None):
        """Create or update an Event row from a SofaScore event payload.

        Expects `home` and `away` to already be Team instances (upserted by the
        caller from payload['homeTeam'] / payload['awayTeam']).
        """
        event_id = payload.get("id")
        if event_id is None:
            return None

        tournament = payload.get("tournament") or {}
        unique_tournament = tournament.get("uniqueTournament") or {}
        category = tournament.get("category") or {}
        season = payload.get("season") or {}
        round_info = payload.get("roundInfo") or {}
        status = payload.get("status") or {}
        home_score = payload.get("homeScore") or {}
        away_score = payload.get("awayScore") or {}

        if sport is None:
            sport_payload = category.get("sport") or {}
            sport_id = sport_payload.get("id")
            if sport_id is not None:
                sport = Sport.objects.upsert_from_payload(sport_payload)

        status_type = (status.get("type") or "")[:32]
        winner_code = payload.get("winnerCode")

        defaults = {
            "slug": (payload.get("slug") or "")[:255],
            "custom_id": (payload.get("customId") or "")[:16],
            "sport": sport,
            "tournament_id": tournament.get("id"),
            "tournament_name": (tournament.get("name") or "")[:255],
            "tournament_slug": (tournament.get("slug") or "")[:255],
            "unique_tournament_id": unique_tournament.get("id"),
            "category_id": category.get("id"),
            "category_name": (category.get("name") or "")[:128] or None,
            "season_id": season.get("id"),
            "season_name": (season.get("name") or "")[:128] or None,
            "round_number": round_info.get("round"),
            "start_time": _utc_from_ts(payload.get("startTimestamp")),
            "status_code": status.get("code") or 0,
            "status_type": status_type,
            "status_description": (status.get("description") or "")[:64],
            "completed": status_type == "finished",
            "home_team": home,
            "away_team": away,
            "home_score": home_score.get("current"),
            "away_score": away_score.get("current"),
            "scores_payload": {"home": home_score, "away": away_score},
            "winner_code": winner_code,
            "winner": _winner_name(winner_code, home, away),
            "feed_locked": bool(payload.get("feedLocked", False)),
        }
        previous = self.filter(id=event_id).only(
            "status_type", "home_score", "away_score"
        ).first()
        obj, _ = self.update_or_create(id=event_id, defaults=defaults)

        if _should_settle(previous, obj):
            # Import locally to avoid circular import (settlement -> models).
            from core.event.odds.settlement import settle_event
            try:
                settle_event(obj)
            except Exception:  # noqa: BLE001 — settlement must not break ingest
                import logging
                logging.getLogger(__name__).exception(
                    "settle_event failed for event=%s", obj.id
                )
        if _should_reopen(previous, obj):
            # Local import: core.game depends on core.event indirectly.
            from core.game.events import reopen_games_for_voided_event
            try:
                reopen_games_for_voided_event(obj)
            except Exception:  # noqa: BLE001 — never break ingest
                import logging
                logging.getLogger(__name__).exception(
                    "reopen_games_for_voided_event failed for event=%s", obj.id
                )
        return obj


class Event(models.Model):
    id = models.BigIntegerField(primary_key=True)
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)

    slug = models.CharField(max_length=255, blank=True)
    custom_id = models.CharField(max_length=16, blank=True)

    sport = models.ForeignKey(
        Sport, on_delete=models.SET_NULL, null=True, blank=True, related_name="events"
    )

    tournament_id = models.IntegerField(null=True, blank=True, db_index=True)
    tournament_name = models.CharField(max_length=255, blank=True)
    tournament_slug = models.CharField(max_length=255, blank=True)
    unique_tournament_id = models.IntegerField(null=True, blank=True)
    category_id = models.IntegerField(null=True, blank=True)
    category_name = models.CharField(max_length=128, null=True, blank=True)
    season_id = models.IntegerField(null=True, blank=True)
    season_name = models.CharField(max_length=128, null=True, blank=True)
    round_number = models.IntegerField(null=True, blank=True)

    start_time = models.DateTimeField(null=True, blank=True, db_index=True)
    status_code = models.IntegerField(default=0)
    status_type = models.CharField(max_length=32, db_index=True, blank=True)
    status_description = models.CharField(max_length=64, blank=True)
    completed = models.BooleanField(default=False)

    home_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="home_events"
    )
    away_team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="away_events"
    )

    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    scores_payload = models.JSONField(default=dict, blank=True)

    winner_code = models.SmallIntegerField(null=True, blank=True)
    winner = models.CharField(max_length=255, null=True, blank=True)
    feed_locked = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = EventManager()

    class Meta:
        db_table = "core_event_event"
        ordering = ["-start_time"]

    def __str__(self):
        home = self.home_team.name if self.home_team else "?"
        away = self.away_team.name if self.away_team else "?"
        return f"{home} vs {away}"
