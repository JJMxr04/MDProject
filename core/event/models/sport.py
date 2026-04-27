"""Sport — the top-level enum-like grouping (BASEBALL, BASKETBALL, FOOTBALL,
HOCKEY, SOCCER…).

Under the SportsGameOdds API the sport identifier is a stable uppercase string
(``"FOOTBALL"``), not a numeric id. We use that string as the primary key so
every reference to a sport is human-readable.

Per-league activation lives on the ``League`` model — flipping a single
league on/off is what controls the cron allowlist; the sport's own ``active``
flag is a derived rollup (any active league in the sport).
"""

from django.db import models


class SportManager(models.Manager):
    def active(self):
        return self.filter(active=True)

    def get_active_sports_obj(self):
        # Backwards-compatible name used by core/event/viewsets/sport.py.
        return self.filter(active=True).order_by("name")

    def upsert_from_sgo(self, payload: dict) -> "Sport | None":
        """Create or update a Sport row from SGO ``GET /sports`` payload."""
        sport_id = payload.get("sportID")
        if not sport_id:
            return None
        obj, _ = self.update_or_create(
            id=sport_id,
            defaults={
                "name": payload.get("name") or sport_id.title(),
                "short_name": (payload.get("shortName") or "")[:48],
            },
        )
        return obj


class Sport(models.Model):
    id = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=64)
    short_name = models.CharField(max_length=48, blank=True)
    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = SportManager()

    class Meta:
        db_table = "core_sport"
        ordering = ["name"]

    def __str__(self):
        return self.name
