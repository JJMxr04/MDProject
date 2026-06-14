"""Progression models (phase 8): seasons, per-season participation, the
permanent player track, an XP ledger, and badges.

Greenfield — see the phase doc for the rank design. Both ranks are
points-ordered; Elo is recorded but not used for ordering v1.
"""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from core.ranking import constants
from core.user.models import User


class Season(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_ranking_season"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:90]
        super().save(*args, **kwargs)

    def clean(self):
        # Cadence is operator data (D-8): any dates allowed, but the ranges
        # of live seasons must not overlap and only one may be ACTIVE.
        if self.end_date and self.start_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})

        live = Season.objects.exclude(pk=self.pk).exclude(status=self.Status.CLOSED)
        if self.status == self.Status.ACTIVE and live.filter(status=self.Status.ACTIVE).exists():
            raise ValidationError({"status": "Another season is already ACTIVE."})
        overlap = live.filter(
            start_date__lte=self.end_date, end_date__gte=self.start_date,
        )
        if overlap.exists():
            raise ValidationError(
                "This season's dates overlap another DRAFT/ACTIVE season."
            )

    @classmethod
    def active(cls):
        """The single ACTIVE season, or None during a gap between seasons."""
        return cls.objects.filter(status=cls.Status.ACTIVE).first()


class SeasonParticipation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="season_participations")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="participations")

    rating = models.FloatField(default=constants.ELO_START)  # seasonal Elo (re-anchors each season)
    season_points = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    games_played = models.IntegerField(default=0)
    potd_wins = models.IntegerField(default=0)
    potd_picks = models.IntegerField(default=0)
    division = models.IntegerField(default=1)
    final_rank = models.IntegerField(null=True, blank=True)  # frozen at season close

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_ranking_participation"
        constraints = [
            models.UniqueConstraint(fields=["user", "season"], name="uniq_user_season"),
        ]
        indexes = [models.Index(fields=["season", "-season_points"])]

    def __str__(self):
        return f"{self.user} @ {self.season.name}: {self.season_points} pts"

    @property
    def win_rate(self) -> float:
        return self.wins / self.games_played if self.games_played else 0.0


class PlayerProgress(models.Model):
    """The permanent track — never resets. ``level``/``xp`` are cosmetic,
    ``global_points`` orders the global rank, ``all_time_rating`` is a
    continuous Elo separate from the seasonal one."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="progress")

    xp = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    global_points = models.IntegerField(default=0)
    lifetime_wins = models.IntegerField(default=0)
    lifetime_losses = models.IntegerField(default=0)
    lifetime_draws = models.IntegerField(default=0)
    lifetime_games = models.IntegerField(default=0)
    all_time_rating = models.FloatField(default=constants.ELO_START)
    # Division a new SeasonParticipation inherits — updated by promotion /
    # relegation at season close (phase 8 increment 2).
    current_division = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_ranking_progress"
        indexes = [models.Index(fields=["-global_points"])]

    def __str__(self):
        return f"{self.user}: L{self.level} ({self.global_points} pts)"

    @property
    def xp_into_level(self) -> int:
        return self.xp - constants.xp_to_reach_level(self.level)

    @property
    def xp_for_next_level(self) -> int:
        return constants.xp_to_reach_level(self.level + 1) - constants.xp_to_reach_level(self.level)


class XpEvent(models.Model):
    """Append-only XP ledger. ``PlayerProgress.xp`` is the cached sum; the
    ledger makes awards auditable and re-tunable by replay."""

    class Source(models.TextChoices):
        MATCH_COMPLETED = "MATCH_COMPLETED", "Match completed"
        MATCH_WIN = "MATCH_WIN", "Match win bonus"
        GOLDEN_HIT = "GOLDEN_HIT", "Golden pick hit"
        POTD_PICK = "POTD_PICK", "POTD pick made"
        POTD_WIN = "POTD_WIN", "POTD pick won"
        POTD_STREAK = "POTD_STREAK", "POTD streak milestone"
        DUEL_WON = "DUEL_WON", "Duel won"
        SEASON_FINISH = "SEASON_FINISH", "Season finish"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="xp_events")
    source = models.CharField(max_length=20, choices=Source.choices)
    amount = models.IntegerField()
    match = models.ForeignKey(
        "core_match.Match", on_delete=models.SET_NULL, null=True, blank=True, related_name="xp_events",
    )
    potd_pick = models.ForeignKey(
        "core_potd.DailyPick", on_delete=models.SET_NULL, null=True, blank=True, related_name="xp_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_ranking_xp_event"
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"{self.user} +{self.amount} ({self.source})"


class Badge(models.Model):
    """Permanent achievement — survives season resets."""

    class Type(models.TextChoices):
        DIVISION_WINNER = "DIVISION_WINNER", "Division winner"
        TOP_THREE = "TOP_THREE", "Top 3 finish"
        PERFECT_WEEK = "PERFECT_WEEK", "Perfect week"
        STREAK = "STREAK", "Streak milestone"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="badges")
    type = models.CharField(max_length=20, choices=Type.choices)
    season = models.ForeignKey(Season, on_delete=models.SET_NULL, null=True, blank=True, related_name="badges")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_ranking_badge"
        indexes = [models.Index(fields=["user", "-earned_at"])]

    def __str__(self):
        return f"{self.user}: {self.get_type_display()}"
