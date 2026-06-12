"""The Section 4 loop metrics, computed from ProductEvent rows.

    python manage.py metrics_report [--days 14]

Three blocks:
  1. D1/D7 cohort retention — signup cohorts by day; retained = has a
     ``session_start`` exactly 1 / 7 days after signup.
  2. Picks per active user, trailing 7 days.
  3. Both-players-return — % of completed matches where BOTH players had
     a ``session_start`` within 72h after completion. Matches completed
     less than 72h ago are excluded (their window is still open).

plan.md Section 4: monetization tuning is pointless until ~30%+ of
testers return in week two — this is the instrument that tells us.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.metrics.models import ProductEvent
from core.user.models import User

RETURN_WINDOW = timedelta(hours=72)


class Command(BaseCommand):
    help = "D1/D7 retention, picks/user/week, both-players-return (plan Section 4)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=14,
            help="How many days of signup cohorts / completions to report (default 14)",
        )

    def handle(self, *args, **options):
        days = options["days"]
        now = timezone.now()
        today = timezone.localdate()

        self._cohort_retention(today, days)
        self._picks_per_user(now)
        self._both_players_return(now, days)

    # -- 1. D1/D7 cohort retention ------------------------------------

    def _cohort_retention(self, today, days):
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"D1/D7 retention — signup cohorts, last {days} days"
        ))
        self.stdout.write(f"{'cohort':<12}{'size':>6}{'D1':>8}{'D7':>8}")

        session_days = self._session_days()

        for offset in range(days, 0, -1):
            cohort_day = today - timedelta(days=offset)
            cohort = list(
                User.objects.filter(created__date=cohort_day)
                .values_list("pk", flat=True)
            )
            if not cohort:
                continue
            d1 = sum(
                1 for uid in cohort
                if cohort_day + timedelta(days=1) in session_days.get(uid, set())
            )
            d7_day = cohort_day + timedelta(days=7)
            d7_applicable = d7_day <= today
            d7 = sum(
                1 for uid in cohort if d7_day in session_days.get(uid, set())
            ) if d7_applicable else None
            self.stdout.write(
                f"{cohort_day.isoformat():<12}{len(cohort):>6}"
                f"{self._pct(d1, len(cohort)):>8}"
                f"{self._pct(d7, len(cohort)) if d7 is not None else '   n/a':>8}"
            )

    def _session_days(self):
        """{user_id: {date, …}} across all session_start events."""
        out: dict = {}
        rows = ProductEvent.objects.filter(
            name="session_start", user__isnull=False,
        ).values_list("user_id", "created_at")
        for uid, created in rows:
            out.setdefault(uid, set()).add(timezone.localtime(created).date())
        return out

    # -- 2. Picks per user per week ------------------------------------

    def _picks_per_user(self, now):
        week_ago = now - timedelta(days=7)
        picks = ProductEvent.objects.filter(
            name="pick_made", created_at__gte=week_ago,
        ).count()
        wau = (
            ProductEvent.objects.filter(
                name="session_start", created_at__gte=week_ago,
                user__isnull=False,
            ).values("user_id").distinct().count()
        )
        rate = f"{picks / wau:.1f}" if wau else "n/a"
        self.stdout.write(self.style.MIGRATE_HEADING("Picks per user — trailing 7 days"))
        self.stdout.write(f"picks={picks}  weekly_active_users={wau}  picks/user/week={rate}")

    # -- 3. Both-players-return ----------------------------------------

    def _both_players_return(self, now, days):
        since = now - timedelta(days=days)
        cutoff = now - RETURN_WINDOW
        completions = ProductEvent.objects.filter(
            name="match_completed",
            created_at__gte=since,
            created_at__lte=cutoff,  # window must have fully elapsed
        ).values_list("created_at", "props")

        total = both = 0
        for completed_at, props in completions:
            p1, p2 = props.get("player_1_id"), props.get("player_2_id")
            if not p1 or not p2:
                continue
            total += 1
            if self._returned(p1, completed_at) and self._returned(p2, completed_at):
                both += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Both-players-return (72h) — completions in last {days} days"
        ))
        if total == 0:
            self.stdout.write("no eligible completed matches yet")
        else:
            self.stdout.write(
                f"matches={total}  both_returned={both}  rate={self._pct(both, total)}"
            )

    @staticmethod
    def _returned(user_id, completed_at) -> bool:
        return ProductEvent.objects.filter(
            user_id=user_id,
            name="session_start",
            created_at__gt=completed_at,
            created_at__lte=completed_at + RETURN_WINDOW,
        ).exists()

    @staticmethod
    def _pct(n, d) -> str:
        return f"{100 * n / d:.0f}%" if d else "n/a"
