"""Reconcile the PRO plan's amount_cents with the PLATFORM_COST env var.

Run after editing the PLATFORM_COST entry in .env::

    python manage.py sync_platform_cost

What it does:

1. Reads ``settings.PLATFORM_COST_CENTS`` (parsed from PLATFORM_COST in
   settings.py — dollars in env, cents in settings).
2. Loads every active non-FREE Plan row (today that's just PRO; the
   loop is future-proof if you add tiers).
3. If a Plan's ``amount_cents`` already matches, leaves it alone.
4. Otherwise updates the row and saves. ``Plan.post_save`` then pushes
   the change to Stripe — minting a new immutable Price and archiving
   the old one (existing subscriptions keep billing at the old number;
   new Checkouts use the new one — that's Stripe's behavior, mirrored
   in catalog.sync_plan_to_stripe).

Unset / empty / malformed PLATFORM_COST: command exits 0 with a notice
and leaves the catalog alone.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from core.billing.models import Plan


class Command(BaseCommand):
    help = "Reconcile the PRO plan's amount_cents with the PLATFORM_COST env var."

    def handle(self, *args, **opts):
        target_cents = getattr(settings, "PLATFORM_COST_CENTS", None)
        if target_cents is None:
            import os
            raw_env = (os.environ.get("PLATFORM_COST") or "").strip()
            if not raw_env:
                self.stdout.write(self.style.NOTICE(
                    "PLATFORM_COST is unset or empty — nothing to sync. "
                    "Set it in .env (e.g. PLATFORM_COST=2.99) and re-run."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"PLATFORM_COST={raw_env!r} couldn't be parsed as a "
                    "decimal dollar amount — fix it in .env and re-run."
                ))
            return

        plans = Plan.objects.exclude(code="FREE").order_by("code")
        if not plans.exists():
            self.stdout.write(self.style.WARNING(
                "No non-FREE plans found. Create one in /admin/billing/plan/ "
                "first, then re-run."
            ))
            return

        changed = 0
        for plan in plans:
            if plan.amount_cents == target_cents:
                self.stdout.write(
                    f"  · {plan.code}: already at {target_cents} cents — unchanged."
                )
                continue
            old = plan.amount_cents
            plan.amount_cents = target_cents
            # save() fires the post_save signal that pushes to Stripe.
            plan.save(update_fields=["amount_cents"])
            changed += 1
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {plan.code}: {old} → {target_cents} cents "
                f"(${target_cents / 100:.2f}). Stripe Price will be "
                f"replaced on next catalog sync (post_save).",
            ))

        if changed == 0:
            self.stdout.write(self.style.NOTICE(
                "All plans already match PLATFORM_COST — no updates needed."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done — {changed} plan{'s' if changed != 1 else ''} updated."
            ))
