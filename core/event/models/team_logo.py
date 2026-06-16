"""TeamLogo — aggregator-sourced crest bytes stored in MDProject's Postgres.

1:1 with Team. Bytes live in a side table (not on Team) so hot Team queries
stay lean. ``status`` is ``ok`` (bytes present) or ``missing`` (aggregator
404 — negative cached until the cooldown elapses).
"""

from __future__ import annotations

from django.db import models


class TeamLogo(models.Model):
    team = models.OneToOneField(
        "core_event.Team",
        on_delete=models.CASCADE,
        related_name="logo",
        primary_key=True,
    )
    image = models.BinaryField(null=True, blank=True, editable=False)
    content_type = models.CharField(max_length=64, null=True, blank=True)
    byte_size = models.PositiveIntegerField(default=0)
    etag = models.CharField(max_length=64, null=True, blank=True)
    # "ok" | "missing"
    status = models.CharField(max_length=16)
    source = models.CharField(max_length=32, default="aggregator")
    fetched = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_team_logo"

    def __str__(self):
        return f"{self.team_id} [{self.status}]"
