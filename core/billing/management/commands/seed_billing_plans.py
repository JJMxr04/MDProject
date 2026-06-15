"""Ensure the FREE + PRO billing plans exist, priced from PLATFORM_COST.

Idempotent (get-or-create by ``code``); safe to run on every deploy. Replaces
the manual "create a Plan in /admin/core_billing/plan/add/" step — set
PLATFORM_COST in the env and let this own the catalog.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Get-or-create FREE + PRO plans, pricing PRO from PLATFORM_COST."

    def handle(self, *args, **options):
        from core.billing.services.seed import ensure_default_plans

        for note in ensure_default_plans():
            self.stdout.write(self.style.SUCCESS(f"  · {note}"))
