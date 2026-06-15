"""Ensure today's Pick of the Day exists (idempotent / get-or-create).

Safe to run on deploy: an existing pick (cron- or admin-created) is returned
untouched, and a missing catalog is reported without failing the deploy.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Ensure today's Pick of the Day exists (idempotent). Safe on deploy."

    def handle(self, *args, **options):
        from core.potd.services import CurationError, curate_pick_of_day

        try:
            potd = curate_pick_of_day()
            self.stdout.write(self.style.SUCCESS(f"Pick of the Day ready: {potd}"))
        except CurationError as exc:
            # Expected when the events catalog is empty/unreachable — the
            # nightly cron will retry. Do not fail the deploy.
            self.stdout.write(self.style.WARNING(f"Pick of the Day not curated: {exc}"))
