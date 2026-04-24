import uuid

from django.db import models

from core.event.models.sport import Sport


def _color(payload, key):
    colors = payload.get("teamColors") or {}
    value = colors.get(key)
    return value[:9] if value else None


class TeamManager(models.Manager):
    def get_by_public_id(self, public_id):
        return self.filter(public_id=public_id).first()

    def upsert_from_payload(self, payload, sport=None):
        """Create or update a Team row from an embedded SofaScore team object.

        Called for every event.homeTeam / event.awayTeam during event ingest —
        zero network calls.
        """
        team_id = payload.get("id")
        if team_id is None:
            return None

        if sport is None:
            sport_payload = payload.get("sport") or {}
            sport_id = sport_payload.get("id")
            if sport_id is not None:
                sport = Sport.objects.upsert_from_payload(sport_payload)

        country = payload.get("country") or {}

        defaults = {
            "name": payload.get("name") or "",
            "slug": payload.get("slug") or "",
            "short_name": (payload.get("shortName") or "")[:64],
            "name_code": (payload.get("nameCode") or "")[:8],
            "gender": (payload.get("gender") or "")[:4],
            "national": bool(payload.get("national", False)),
            "sport": sport,
            "country_name": country.get("name"),
            "country_alpha2": country.get("alpha2"),
            "country_alpha3": country.get("alpha3"),
            "primary_color": _color(payload, "primary"),
            "secondary_color": _color(payload, "secondary"),
            "text_color": _color(payload, "text"),
            "user_count": int(payload.get("userCount") or 0),
        }
        obj, _ = self.update_or_create(id=team_id, defaults=defaults)
        return obj


def logo_upload_path(instance, filename):
    return f"teamLogos/{instance.country_alpha2 or 'NA'}/{instance.id}/{filename}"


class Team(models.Model):
    id = models.IntegerField(primary_key=True)
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255, db_index=True, blank=True)
    short_name = models.CharField(max_length=64, blank=True)
    name_code = models.CharField(max_length=8, blank=True)
    gender = models.CharField(max_length=4, blank=True)
    national = models.BooleanField(default=False)

    sport = models.ForeignKey(
        Sport, on_delete=models.SET_NULL, null=True, blank=True, related_name="teams"
    )

    country_name = models.CharField(max_length=128, null=True, blank=True)
    country_alpha2 = models.CharField(max_length=4, null=True, blank=True)
    country_alpha3 = models.CharField(max_length=4, null=True, blank=True)

    primary_color = models.CharField(max_length=9, null=True, blank=True)
    secondary_color = models.CharField(max_length=9, null=True, blank=True)
    text_color = models.CharField(max_length=9, null=True, blank=True)

    logo_url = models.ImageField(upload_to=logo_upload_path, null=True, blank=True)
    user_count = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = TeamManager()

    class Meta:
        db_table = "core_team"
        ordering = ["name"]

    def __str__(self):
        return self.name
