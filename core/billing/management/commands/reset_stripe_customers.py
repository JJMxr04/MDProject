"""Force every user to a freshly-minted Stripe Customer.

Use this when rotating Stripe test credentials (or any time you want the
local ``stripe_customer_id`` column to align with the *current* Stripe
account). For each matching user we:

1. Best-effort ``stripe.Customer.delete`` of the old id (skip on 404 —
   the old account is likely already gone in test mode).
2. ``stripe.Customer.create`` a fresh one with the user's email + name +
   metadata.
3. ``User.stripe_customer_id`` ← the new ``cus_...``.

Refuses to run without ``--yes`` so a stray invocation can't silently
overwrite production. ``--dry-run`` reports who *would* be touched.

Typical:
    python manage.py reset_stripe_customers --dry-run
    python manage.py reset_stripe_customers --yes --exclude-staff

Per-user wall time: ~0.5–1.0s (one delete + one create round-trip).
Throttled with ``--sleep`` to keep Stripe rate limiting at bay.
"""

from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand, CommandError

from core.billing.services.customer import ResetReport, reset_customer
from core.user.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Delete existing Stripe Customers (best-effort) and create fresh "
        "ones for every user. Use after rotating Stripe credentials."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help=(
                "Required to actually run. Without it we refuse — this "
                "command overwrites stripe_customer_id on every matching "
                "user, so an accidental run is destructive."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List who would be touched. No Stripe calls, no DB writes.",
        )
        parser.add_argument(
            "--exclude-staff",
            action="store_true",
            help="Skip is_staff / is_superuser / is_admin users.",
        )
        parser.add_argument(
            "--only-with-id",
            action="store_true",
            help=(
                "Limit to users that currently have a non-empty "
                "stripe_customer_id (i.e. only re-mint the ones tied to "
                "the previous Stripe account)."
            ),
        )
        parser.add_argument(
            "--email",
            default="",
            help="Run only for the user with this exact email.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.25,
            help="Seconds between users (default: 0.25). Throttles Stripe.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N successful resets (0 = no limit).",
        )

    def handle(
        self, *, yes, dry_run, exclude_staff, only_with_id, email, sleep, limit,
        **opts,
    ):
        if not yes and not dry_run:
            raise CommandError(
                "Refusing to run without --yes (destructive). Add --dry-run "
                "to preview, or --yes to commit."
            )

        qs = User.objects.all().order_by("pk")
        if email:
            qs = qs.filter(email__iexact=email)
        if exclude_staff:
            qs = qs.exclude(is_staff=True).exclude(is_superuser=True).exclude(is_admin=True)
        if only_with_id:
            qs = qs.exclude(stripe_customer_id="")
        # Skip users without an email — stripe.Customer.create needs one
        # for the rest of the flow (Checkout, invoices) to mean anything.
        qs = qs.exclude(email="")

        total = qs.count()
        self.stdout.write(f"Found {total} matching user(s).")
        if total == 0 or dry_run:
            if dry_run:
                for u in qs[:50]:
                    self.stdout.write(
                        f"  would reset pk={u.pk} email={u.email} "
                        f"old={u.stripe_customer_id or '—'}"
                    )
                if total > 50:
                    self.stdout.write(f"  … (+{total - 50} more)")
                self.stdout.write(self.style.SUCCESS("dry-run — no changes made"))
            return

        done = failed = 0
        for user in qs.iterator(chunk_size=100):
            report: ResetReport = reset_customer(user)
            if report.error:
                failed += 1
                self.stderr.write(self.style.WARNING(
                    f"FAIL pk={report.user_id} email={report.email}: {report.error}"
                ))
            else:
                done += 1
                # Short status line per user — ops grep target.
                deleted = "deleted-old" if report.deleted_old else (
                    f"skip-delete[{report.delete_skipped_reason}]"
                )
                self.stdout.write(
                    f"  ok pk={report.user_id} email={report.email} "
                    f"{deleted} new={report.new_customer_id}"
                )
            if limit and done >= limit:
                self.stdout.write(f"  limit ({limit}) reached — stopping early")
                break
            time.sleep(sleep)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {done} reset, {failed} failed."
        ))
