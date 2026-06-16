"""Team — composite-PK model scoped per league.

SGO defines teams per league, so the same physical club can appear with
different ``teamID``s across leagues (``ARSENAL_EPL`` vs
``ARSENAL_UEFA_CHAMPIONS_LEAGUE``). We capture that explicitly:

- ``id`` is a synthesized string ``"{league_id}:{team_id}"``.
- ``team_id`` carries the raw SGO ``teamID``.
- ``unique_together = ("league", "team_id")`` enforces one row per pair.

Teams arrive embedded in event payloads — zero extra API calls.
"""

import uuid

from django.db import models

from core.event.models.league import League
from core.event.models.sport import Sport


class TeamManager(models.Manager):
    def get_by_public_id(self, public_id):
        return self.filter(public_id=public_id).first()

    @staticmethod
    def synth_pk(league_id: str, team_id: str) -> str:
        return f"{league_id}:{team_id}"

    def upsert_from_spec(self, spec) -> "Team | None":
        """Create or update a Team row from a ``TeamSpec`` produced by
        ``core.event.odds.sgo_normalize.event_spec_from_payload``.
        """
        if not spec.team_id or not spec.league_id:
            return None
        try:
            league = League.objects.select_related("sport").get(id=spec.league_id)
        except League.DoesNotExist:
            return None
        pk = self.synth_pk(spec.league_id, spec.team_id)
        defaults = {
            "league": league,
            "team_id": spec.team_id,
            "sport": league.sport,
            "name_long": (spec.name_long or spec.team_id)[:128],
            "name_medium": (spec.name_medium or spec.team_id)[:64],
            "name_short": (spec.name_short or spec.team_id)[:32],
            "primary_color": spec.primary_color,
            "secondary_color": spec.secondary_color,
            "primary_contrast": spec.primary_contrast,
            "secondary_contrast": spec.secondary_contrast,
            "stat_entity_id": (spec.stat_entity_id or "")[:8],
        }
        obj, _ = self.update_or_create(id=pk, defaults=defaults)
        return obj


class Team(models.Model):
    id = models.CharField(max_length=80, primary_key=True)
    public_id = models.UUIDField(
        db_index=True, unique=True, default=uuid.uuid4, editable=False
    )

    league = models.ForeignKey(
        League, on_delete=models.PROTECT, related_name="teams"
    )
    team_id = models.CharField(max_length=48)

    sport = models.ForeignKey(
        Sport, on_delete=models.PROTECT, null=True, blank=True, related_name="teams"
    )

    name_long = models.CharField(max_length=128)
    name_medium = models.CharField(max_length=64, blank=True)
    name_short = models.CharField(max_length=32, blank=True)

    primary_color = models.CharField(max_length=9, null=True, blank=True)
    secondary_color = models.CharField(max_length=9, null=True, blank=True)
    primary_contrast = models.CharField(max_length=9, null=True, blank=True)
    secondary_contrast = models.CharField(max_length=9, null=True, blank=True)

    stat_entity_id = models.CharField(max_length=8, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = TeamManager()

    class Meta:
        db_table = "core_team"
        ordering = ["name_long"]
        unique_together = [("league", "team_id")]
        indexes = [
            models.Index(fields=["league", "team_id"]),
        ]

    @property
    def name(self) -> str:
        # Backwards-compatible attribute used by serializers/scoring/admin.
        return self.name_long

    @property
    def short_name(self) -> str:
        return self.name_short or self.name_medium or self.name_long

    @property
    def logo_url(self) -> str | None:
        """Serve-endpoint URL for this team's crest, or None when absent.

        Returns a string (not a FieldFile) so templates' ``{{ team.logo_url }}``
        and ``{% if team.logo_url %}`` keep working after the S3 ImageField was
        retired. Routes persisted surfaces (matches/duels/events/teams) to
        MDProject's own bytes. Callers rendering many teams should
        ``select_related("logo")`` to avoid an N+1.
        """
        from core.event.models.team_logo import TeamLogo

        try:
            logo = self.logo
        except TeamLogo.DoesNotExist:
            return None
        if logo.status != "ok":
            return None
        from django.urls import reverse

        return reverse("team-logo", kwargs={"team_id": self.id})

    def __str__(self):
        return self.name_long
