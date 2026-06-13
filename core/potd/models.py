"""Pick of the Day (plan Phase 6).

One free curated game per day — everyone picks within a single locked
market (mirroring the Golden Game UX), streaks count consecutive *days
picked* (kinder than consecutive wins), wins feed the leaderboard.

The product day is the **America/New_York calendar date** (sports prime
time lives there), independent of the server's UTC TIME_ZONE.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db import models, transaction
from django.utils import timezone

from core.event.models import Event, Market, Selection
from core.user.models import User


POTD_TZ = ZoneInfo("America/New_York")


def potd_today():
    """Today's product date (NY calendar day)."""
    return timezone.now().astimezone(POTD_TZ).date()


class PickError(Exception):
    """User-facing pick validation failure (mirrors core.game.PickError)."""


class PickOfDayManager(models.Manager):
    def for_date(self, date):
        return (
            self.select_related(
                "event", "event__home_team", "event__away_team",
                "event__league", "market",
            )
            .filter(date=date)
            .first()
        )

    def for_today(self):
        return self.for_date(potd_today())


class PickOfDay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    # Local mirror of the aggregator event (ensure_chain at curation time) —
    # same string-PK Event row the rest of the product uses.
    event = models.ForeignKey(
        Event, on_delete=models.PROTECT, related_name="potd_days",
    )
    # Everyone picks within this one market (Golden Game pattern). Curation
    # prefers FULL_GAME MONEYLINE and mirrors EVERY priced selection so all
    # sides (incl. DRAW on 3-way soccer lines) are pickable.
    market = models.ForeignKey(
        Market, on_delete=models.PROTECT, related_name="potd_days",
    )
    # Picks close here — the event kickoff.
    lock_time = models.DateTimeField()
    # True when a human placed/replaced this row in the admin; the curation
    # cron never overwrites a manually curated day.
    manually_curated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PickOfDayManager()

    class Meta:
        db_table = "core_potd"
        verbose_name = "Pick of the Day"
        verbose_name_plural = "Picks of the Day"

    def __str__(self):
        return f"PotD {self.date}: {self.event_id}"

    @property
    def is_locked(self):
        return self.lock_time <= timezone.now()


class DailyPickResult(models.TextChoices):
    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    # Postponed/canceled/push — neither a win nor a loss; the picked-day
    # streak is unaffected either way (streak = days picked, not wins).
    VOID = "VOID"


class DailyPickManager(models.Manager):
    @transaction.atomic
    def record_pick(self, *, user, potd, selection):
        """One-tap pick: validate, write the row, advance the streak.

        Raises PickError on closed window / wrong market / repeat pick —
        picking twice the same day is impossible (DB-unique backed).
        """
        if potd.is_locked:
            raise PickError("Today's pick is closed — the game has started.")
        if selection.market_id != potd.market_id:
            raise PickError("That selection isn't part of today's pick.")

        if self.filter(user=user, potd=potd).exists():
            raise PickError("You already made today's pick.")
        pick = self.create(user=user, potd=potd, selection=selection)

        # Streak = consecutive product days with a pick. Computed at pick
        # time off the user's last pick date — no settlement dependency.
        locked_user = User.objects.select_for_update().get(pk=user.pk)
        if locked_user.potd_last_pick_date == potd.date - timedelta(days=1):
            locked_user.potd_current_streak += 1
        else:
            locked_user.potd_current_streak = 1
        locked_user.potd_best_streak = max(
            locked_user.potd_best_streak, locked_user.potd_current_streak,
        )
        locked_user.potd_last_pick_date = potd.date
        locked_user.save(update_fields=[
            "potd_current_streak", "potd_best_streak", "potd_last_pick_date",
        ])
        # Keep the in-memory instance honest for callers/templates.
        user.potd_current_streak = locked_user.potd_current_streak
        user.potd_best_streak = locked_user.potd_best_streak
        user.potd_last_pick_date = locked_user.potd_last_pick_date

        from core.metrics.models import track
        track(user, "potd_picked",
              potd_id=str(potd.pk), potd_date=str(potd.date),
              selection_id=selection.pk,
              streak=locked_user.potd_current_streak)
        return pick

    def sync_pending(self):
        """Pull settled selection statuses into DailyPick.result.

        Settlement happens inline in the event-upsert path (no signal), so
        results are synced opportunistically: from the nightly cron and
        before leaderboard renders. Idempotent bulk updates; returns the
        number of rows that left PENDING.
        """
        pending = self.filter(result=DailyPickResult.PENDING)
        changed = 0
        changed += pending.filter(
            selection__settlement_status="WON",
        ).update(result=DailyPickResult.WON)
        changed += pending.filter(
            selection__settlement_status="LOST",
        ).update(result=DailyPickResult.LOST)
        changed += pending.filter(
            selection__settlement_status__in=("PUSH", "VOID"),
        ).update(result=DailyPickResult.VOID)
        return changed


class DailyPick(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="daily_picks",
    )
    potd = models.ForeignKey(
        PickOfDay, on_delete=models.CASCADE, related_name="picks",
    )
    selection = models.ForeignKey(
        Selection, on_delete=models.PROTECT, related_name="daily_picks",
    )
    result = models.CharField(
        max_length=10,
        choices=DailyPickResult.choices,
        default=DailyPickResult.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DailyPickManager()

    class Meta:
        db_table = "core_daily_pick"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "potd"], name="uq_daily_pick_user_potd",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} → {self.selection_id} ({self.result})"
