"""Plan → Stripe catalog sync.

The local ``Plan`` row is the source of truth. When admin saves it, we
push the change to Stripe via API and store the returned IDs.

Idempotency:
- Re-saving a Plan with no field changes is a no-op (Product.modify with
  the same values is fine; Price isn't touched because ``_price_drifted``
  returns False).
- Prices are **immutable** in Stripe — ``unit_amount`` and ``recurring``
  can't be modified. If those change, we archive the old Price and mint
  a new one. Existing Subscriptions on the old Price keep billing at the
  old price (Stripe's behavior, not ours); new Checkouts use the new one.

The FREE plan is skipped — it's local-only and never appears in Stripe.

See subscription-plan/03-stripe-integration.md §2.
"""

from __future__ import annotations

import logging

import stripe

# Ensure module-level configure() has run before any call below.
from core.billing import stripe_client  # noqa: F401
from core.billing.models import Plan

logger = logging.getLogger(__name__)


def sync_plan_to_stripe(plan: Plan) -> None:
    """Push ``plan`` to Stripe. Updates ``stripe_product_id`` /
    ``stripe_price_id`` columns in-place when the IDs are minted /
    rotated. Idempotent — safe to call from a post_save signal that
    fires on every save."""
    if plan.code == "FREE":
        return  # local-only

    # Product — create on first sync, update name/metadata on subsequent.
    if not plan.stripe_product_id:
        product = stripe.Product.create(
            name=plan.name,
            metadata={"plan_code": plan.code},
            active=plan.is_active,
        )
        Plan.objects.filter(pk=plan.pk).update(stripe_product_id=product.id)
        plan.stripe_product_id = product.id
        logger.info("created Stripe Product %s for plan %s", product.id, plan.code)
    else:
        stripe.Product.modify(
            plan.stripe_product_id,
            name=plan.name,
            active=plan.is_active,
        )

    # Price — Stripe Prices are immutable on amount/currency/interval.
    # On any change to those fields we archive the old Price and mint a
    # new one. Subscriptions already on the old Price keep billing at the
    # old number (Stripe's behavior); new Checkout sessions use the new.
    needs_new_price = (
        not plan.stripe_price_id or _price_drifted(plan)
    )
    if needs_new_price:
        if plan.stripe_price_id:
            try:
                stripe.Price.modify(plan.stripe_price_id, active=False)
                logger.info(
                    "archived Stripe Price %s (replaced)", plan.stripe_price_id,
                )
            except stripe.error.StripeError as exc:
                # Archive failure shouldn't block creating the new one.
                logger.warning(
                    "failed to archive old Price %s: %s",
                    plan.stripe_price_id, exc,
                )
        price = stripe.Price.create(
            product=plan.stripe_product_id,
            unit_amount=plan.amount_cents,
            currency=plan.currency,
            recurring={"interval": plan.interval},
            metadata={"plan_code": plan.code},
        )
        Plan.objects.filter(pk=plan.pk).update(stripe_price_id=price.id)
        plan.stripe_price_id = price.id
        logger.info("created Stripe Price %s for plan %s", price.id, plan.code)


def _price_drifted(plan: Plan) -> bool:
    """Return True iff the local Plan's amount/currency/interval differs
    from what Stripe has on file for ``plan.stripe_price_id``. Used to
    decide whether to mint a replacement Price."""
    if not plan.stripe_price_id:
        return True
    try:
        live = stripe.Price.retrieve(plan.stripe_price_id)
    except stripe.error.StripeError as exc:
        logger.warning(
            "could not fetch Price %s — assuming drift: %s",
            plan.stripe_price_id, exc,
        )
        return True
    if live.unit_amount != plan.amount_cents:
        return True
    if (live.currency or "").lower() != plan.currency.lower():
        return True
    recurring = live.recurring or {}
    if recurring.get("interval") != plan.interval:
        return True
    return False
