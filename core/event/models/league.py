"""League — the SportsGameOdds ``leagueID`` (e.g., ``NFL``, ``UEFA_CHAMPIONS_LEAGUE``).

Center of gravity for the cron allowlist. Each row carries:
- ``active`` toggle — drives the per-league ingest loop
- ``refresh_cadence_minutes`` — how often we re-pull this league's events
- ``last_refreshed_at`` — bookkeeping for the cadence check

Adding a new league after a tier upgrade is a single fixture row.
"""

from django.db import models

from core.event.models.sport import Sport


class LeagueManager(models.Manager):
    def active(self):
        return self.filter(active=True)

    def upsert_from_sgo(self, payload: dict) -> "League | None":
        """Create or update a League row from SGO ``GET /leagues`` payload."""
        league_id = payload.get("leagueID")
        sport_id = payload.get("sportID")
        if not league_id or not sport_id:
            return None
        sport, _ = Sport.objects.get_or_create(
            id=sport_id, defaults={"name": sport_id.title()}
        )
        obj, _ = self.update_or_create(
            id=league_id,
            defaults={
                "sport": sport,
                "name": payload.get("name") or league_id,
                "short_name": (payload.get("shortName") or "")[:48],
            },
        )
        return obj

    def is_due(self, league: "League", now=None) -> bool:
        """Has this league's last_refreshed_at fallen behind its cadence?

        With ``settings.EVENTS_DEBUG_FORCE_FRESH=True`` cadence is bypassed —
        every active league is always considered due. For local dev against
        the simulator only.
        """
        from django.conf import settings
        from django.utils import timezone

        if not league.active:
            return False
        if getattr(settings, "EVENTS_DEBUG_FORCE_FRESH", False):
            return True
        if league.last_refreshed_at is None:
            return True
        elapsed = (now or timezone.now()) - league.last_refreshed_at
        cadence_seconds = (league.refresh_cadence_minutes or 720) * 60
        return elapsed.total_seconds() >= cadence_seconds


class League(models.Model):
    id = models.CharField(max_length=48, primary_key=True)
    sport = models.ForeignKey(
        Sport, on_delete=models.PROTECT, related_name="leagues"
    )
    name = models.CharField(max_length=128)
    short_name = models.CharField(max_length=48, blank=True)

    active = models.BooleanField(default=False)
    refresh_cadence_minutes = models.PositiveIntegerField(default=720)
    last_refreshed_at = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = LeagueManager()

    class Meta:
        db_table = "core_league"
        ordering = ["sport_id", "name"]
        indexes = [
            models.Index(fields=["sport", "active"]),
        ]

    def __str__(self):
        return f"{self.id} ({self.sport_id})"
