"""``python manage.py sync_kill_switch`` — reconcile Stripe sub state
against the current ``ANALYTICS_FREE_FOR_ALL`` setting.

When the kill-switch is ON, every active/trialing PRO subscription gets
``pause_collection={"behavior": "void"}`` on Stripe — Stripe stops
attempting to charge the card; any invoices that would have been
generated are voided rather than dunning the user. The local
Subscription row keeps its ``active`` status (the sub is *paused*, not
canceled).

When the kill-switch is OFF, any paused sub gets ``pause_collection``
cleared — billing resumes on the next normal cycle.

Idempotent — safe to run repeatedly or out of order. Reads Stripe to
discover current pause state, so no local "we paused these"
bookkeeping is required.

Usage:
    ./manage.py sync_kill_switch              # reconcile against current setting
    ./manage.py sync_kill_switch --dry-run    # report intended changes, no API calls
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

import stripe

from core.billing import stripe_client  # noqa: F401
from core.billing.models import Subscription

logger = logging.getLogger(__name__)


_PAUSE_BEHAVIOR = "void"
_RECONCILABLE_STATUSES = ("active", "trialing")


class Command(BaseCommand):
    help = (
        "Pause / resume Stripe subscription collection to match the "
        "ANALYTICS_FREE_FOR_ALL setting. Run after flipping the env var."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print intended changes without calling Stripe.",
        )

    def handle(self, *args, **options):
        if not settings.STRIPE_SECRET_KEY:
            self.stderr.write(
                "STRIPE_SECRET_KEY is unset — refusing to run."
            )
            return

        free_for_all = getattr(settings, "ANALYTICS_FREE_FOR_ALL", False)
        desired = "paused" if free_for_all else "active"
        self.stdout.write(
            f"ANALYTICS_FREE_FOR_ALL={free_for_all} — desired collection state: {desired}"
        )

        qs = Subscription.objects.filter(
            status__in=_RECONCILABLE_STATUSES,
        ).exclude(stripe_subscription_id="").select_related("user")

        total = qs.count()
        if not total:
            self.stdout.write("No active/trialing Stripe subscriptions on file.")
            return

        self.stdout.write(f"Inspecting {total} subscription(s)…")

        paused = 0
        resumed = 0
        skipped = 0
        errors = 0

        for sub in qs:
            try:
                live = stripe.Subscription.retrieve(sub.stripe_subscription_id)
            except stripe.error.StripeError as exc:
                self.stderr.write(
                    f"  ! {sub.user.email}: retrieve failed — {exc.user_message or exc}"
                )
                errors += 1
                continue

            is_paused = bool(live.pause_collection)
            label = sub.user.email

            if free_for_all and not is_paused:
                if options["dry_run"]:
                    self.stdout.write(f"  → would PAUSE {label} ({live.id})")
                else:
                    try:
                        stripe.Subscription.modify(
                            live.id,
                            pause_collection={"behavior": _PAUSE_BEHAVIOR},
                        )
                        self.stdout.write(f"  ✓ paused {label} ({live.id})")
                    except stripe.error.StripeError as exc:
                        self.stderr.write(
                            f"  ! pause failed for {label}: "
                            f"{exc.user_message or exc}"
                        )
                        errors += 1
                        continue
                paused += 1
            elif not free_for_all and is_paused:
                if options["dry_run"]:
                    self.stdout.write(f"  → would RESUME {label} ({live.id})")
                else:
                    try:
                        stripe.Subscription.modify(live.id, pause_collection="")
                        self.stdout.write(f"  ✓ resumed {label} ({live.id})")
                    except stripe.error.StripeError as exc:
                        self.stderr.write(
                            f"  ! resume failed for {label}: "
                            f"{exc.user_message or exc}"
                        )
                        errors += 1
                        continue
                resumed += 1
            else:
                skipped += 1

        verb = "Would" if options["dry_run"] else "Did"
        self.stdout.write("")
        self.stdout.write(
            f"{verb}: paused={paused}, resumed={resumed}, "
            f"already-in-desired-state={skipped}, errors={errors}"
        )
