"""One-shot backfill: mirror every existing MDProject User into the
aggrigator as a FREE tenant_user (per-user bet attribution, plan §6.4).

Since the service-key cutover (roadmap Phase 2) NO per-user API key is
stored — outbound auth rides the single service key in aggrigator_client,
and per-user data calls assert X-Acting-User. This command only ensures
the tenant_user rows exist.

Idempotent — re-running skips users whose ``aggrigator_external_id`` is
already set, and the aggrigator-side ``POST /v1/internal/users`` is also
idempotent (200 when the user already exists), so a partially-completed
run is safe to resume.

Typical wall time: ~0.1–0.5s per user with --sleep 0.1. Run under
tmux/screen so a dropped SSH doesn't kill it.
"""

from __future__ import annotations

import logging
import time

from django.core.management.base import BaseCommand

from core.billing.models import Plan, Subscription
from core.billing.services import aggrigator_internal
from core.user.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Mirror every MDProject User into the aggrigator as a FREE "
        "tenant_user (no per-user keys — service-key model). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count how many users would be provisioned. Don't call the aggrigator.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="QuerySet iterator chunk size (default: 50).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=0.1,
            help="Seconds between requests; throttles the aggrigator (default: 0.1).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after N successful provisions (0 = no limit). Useful for staging.",
        )

    def handle(self, *, dry_run, batch_size, sleep, limit, **opts):
        free = Plan.objects.filter(code="FREE", is_active=True).first()
        if free is None:
            self.stderr.write(self.style.ERROR(
                "No active FREE Plan row — create one via Django admin or:\n"
                "  Plan.objects.create(code='FREE', name='Free', amount_cents=0, "
                "currency='usd', interval='month', features={'analytics': False})"
            ))
            return

        # Pass 1: ensure every User has a Subscription row. Cheap, local,
        # idempotent. This catches users who were already mirrored (e.g.
        # by a partial prior run) but somehow lack a Subscription.
        sub_created = 0
        for user in User.objects.iterator(chunk_size=batch_size):
            _, created = Subscription.objects.get_or_create(
                user=user,
                defaults={"plan": free, "status": "active"},
            )
            if created:
                sub_created += 1
        if sub_created:
            self.stdout.write(f"Created {sub_created} missing Subscription row(s)")

        # Pass 2: mirror unmirrored users into the aggrigator.
        qs = User.objects.filter(aggrigator_external_id__isnull=True).order_by("pk")
        total = qs.count()
        self.stdout.write(f"Found {total} user(s) needing aggrigator provisioning")
        if dry_run:
            self.stdout.write(self.style.SUCCESS("dry-run — exiting"))
            return
        if total == 0:
            self.stdout.write(self.style.SUCCESS("nothing to do"))
            return

        done = failed = skipped = 0

        for user in qs.iterator(chunk_size=batch_size):
            try:
                # Returned key (if any) deliberately discarded — service-key
                # model; tenant_user existence is all we need.
                aggrigator_internal.provision_user(user, tier="FREE")
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.WARNING(
                    f"FAIL pk={user.pk} email={user.email}: {exc}"
                ))
                time.sleep(sleep)
                continue

            User.objects.filter(pk=user.pk).update(
                aggrigator_external_id=user.public_id,
            )

            done += 1
            if done % 100 == 0:
                self.stdout.write(f"  progress: {done}/{total}")
            if limit and done >= limit:
                self.stdout.write(f"  limit ({limit}) reached — stopping early")
                break
            time.sleep(sleep)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {done} provisioned, {failed} failed, {skipped} skipped."
        ))
