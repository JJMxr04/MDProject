"""Run the idempotent periodic tasks once, on deploy.

Goal: when the project deploys, recurring state (today's Pick of the Day, the
active season, due settlements, etc.) is ensured immediately instead of waiting
for the next midnight cron — using get-or-create semantics so nothing is ever
duplicated ("don't remake them if they're already there").

Only IDEMPOTENT tasks are run here. The two date-windowed tournament tasks are
intentionally skipped:
  * ``tournament_cron_bracketMaker``    — builds a bracket for tournaments
    starting tomorrow; re-firing could create a second bracket.
  * ``tournament_cron_2_day_reminder``  — emails players; it has no "sent"
    guard, so re-firing would send duplicate reminders.
Those stay on their daily schedule. Every step is isolated: one failure (e.g.
an unreachable catalog or Stripe) is logged and never aborts the deploy.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Idempotently ensure recurring state on deploy (get-or-create; never duplicates)."

    def handle(self, *args, **options):
        for label, step in self._steps():
            try:
                result = step()
                self.stdout.write(self.style.SUCCESS(f"[bootstrap] {label}: {result or 'ok'}"))
            except Exception as exc:  # noqa: BLE001 — never let one step fail the deploy
                self.stdout.write(self.style.WARNING(f"[bootstrap] {label}: skipped ({exc})"))

    def _steps(self):
        return [
            ("pick of the day", self._potd),
            ("season lifecycle", self._season_lifecycle),
            ("complete matches", self._complete_matches),
            ("sync POTD results", self._potd_results),
            ("expire invites", self._expire_invites),
            ("reconcile subscriptions", self._reconcile_subscriptions),
        ]

    def _potd(self):
        from core.potd.services import CurationError, curate_pick_of_day
        try:
            return f"ready: {curate_pick_of_day()}"
        except CurationError as exc:
            return f"not curated yet ({exc})"

    def _season_lifecycle(self):
        from core.ranking.lifecycle import run_lifecycle
        return str(run_lifecycle())

    def _complete_matches(self):
        from core.match.crons.matchUpdate import MatchCron
        MatchCron().completeMatches()
        return "ok"

    def _potd_results(self):
        from core.potd.models import DailyPick
        return f"{DailyPick.objects.sync_pending()} settled"

    def _expire_invites(self):
        from core.mail.models import Invite
        return f"{Invite.objects.expire_stale()} expired"

    def _reconcile_subscriptions(self):
        from core.billing.services.reconcile import reconcile_subscriptions
        reconcile_subscriptions()
        return "ok"
