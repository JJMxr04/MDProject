"""Idempotent get-or-create of the billing catalog (FREE + PRO).

Lets the deploy own the plan rows so an operator never has to create them by
hand in the admin — the price comes from the ``PLATFORM_COST`` env var. Saving
the PRO row fires the ``Plan.post_save`` signal that pushes the Product/Price
to Stripe (when ``STRIPE_SECRET_KEY`` is configured).
"""

from __future__ import annotations

from django.conf import settings

from core.billing.models import Plan

# Fallback only used the very first time PRO is created with PLATFORM_COST unset.
_DEFAULT_PRO_CENTS = 999


def ensure_default_plans() -> list[str]:
    """Ensure FREE + PRO exist; price PRO from ``PLATFORM_COST_CENTS``.

    Never duplicates (keyed on ``code``). Returns a list of human-readable
    notes for logging.
    """
    notes: list[str] = []

    # FREE — synthetic, local-only (no Stripe IDs). Subscriptions point here
    # by default, and the signup signal looks it up by (code=FREE, is_active).
    _, created = Plan.objects.get_or_create(
        code="FREE",
        defaults={
            "name": "Free",
            "amount_cents": 0,
            "is_active": True,
            "features": {"analytics": False},
        },
    )
    notes.append(f"FREE {'created' if created else 'exists'}")

    # PRO — price driven by the env.
    target = getattr(settings, "PLATFORM_COST_CENTS", None)
    pro, created = Plan.objects.get_or_create(
        code="PRO",
        defaults={
            "name": "Pro",
            "amount_cents": target if target is not None else _DEFAULT_PRO_CENTS,
            "currency": "usd",
            "interval": "month",
            "trial_days": 0,
            "features": {"analytics": True},
            "is_active": True,
        },
    )
    if created:
        # The post_save signal already pushed Product+Price to Stripe.
        notes.append(f"PRO created at {pro.amount_cents}c")
    elif target is not None and pro.amount_cents != target:
        old = pro.amount_cents
        pro.amount_cents = target
        # Re-save re-pushes to Stripe (new immutable Price, old archived).
        pro.save(update_fields=["amount_cents"])
        notes.append(f"PRO price {old}c -> {target}c")
    else:
        notes.append("PRO exists")

    return notes
