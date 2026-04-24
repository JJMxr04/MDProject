from django.db import models


class SportManager(models.Manager):
    def active(self):
        return self.filter(active=True)

    def get_by_slug(self, slug):
        return self.filter(slug=slug).first()

    def upsert_from_payload(self, payload):
        sport_id = payload.get("id")
        if sport_id is None:
            return None
        obj, _ = self.update_or_create(
            id=sport_id,
            defaults={
                "slug": payload.get("slug") or "",
                "name": payload.get("name") or "",
            },
        )
        return obj


class Sport(models.Model):
    id = models.IntegerField(primary_key=True)
    slug = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    active = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = SportManager()

    class Meta:
        db_table = "core_sport"
        ordering = ["name"]

    def __str__(self):
        return self.name
