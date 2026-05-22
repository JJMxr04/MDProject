"""Billing landing page — current plan + buttons to upgrade / manage."""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

import stripe

from core.billing import stripe_client  # noqa: F401
from core.billing.entitlement import user_can_access_analytics
from core.billing.models import Plan

logger = logging.getLogger(__name__)

# Cap on the invoice list rendered inline. Older invoices are still
# reachable from the Stripe-hosted Customer Portal "Billing history" tab.
_INVOICE_LIST_LIMIT = 24


@login_required(login_url="/auth/login/")
def billing_index(request):
    """Shows the current Subscription state with action buttons.

    - FREE → "Upgrade to PRO" CTA
    - PRO (active/trialing) → "Manage subscription" (Customer Portal link)
    - past_due → grace-period banner + "Update payment method" CTA
    - canceled/unpaid → "Resubscribe" CTA

    When ``ANALYTICS_FREE_FOR_ALL`` is on, the template hides the
    upgrade CTA and shows a free-mode banner instead. Users with an
    actual Stripe subscription still see their plan/status and a
    "Manage subscription" button so they can cancel.
    """
    # Same defensive access as the entitlement helper — never trust the
    # implicit reverse OneToOne, which raises DoesNotExist (not
    # AttributeError) when the row's missing.
    from core.billing.entitlement import _safe_subscription
    sub = _safe_subscription(request.user)
    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    # has_paid_sub = real Stripe subscription (drives invoice list +
    # cancel button visibility). Distinct from is_pro_active, which
    # also lights up for kill-switch-entitled FREE users so the
    # template still shows "Open Analytics →".
    has_paid_sub = bool(
        sub
        and sub.stripe_subscription_id
        and sub.plan.features.get("analytics") is True
        and sub.status in ("trialing", "active", "past_due")
    )
    invoices = _list_invoices(request.user) if request.user.stripe_customer_id else []
    free_for_all = getattr(settings, "ANALYTICS_FREE_FOR_ALL", False)
    # "Your paid sub is paused right now" banner only makes sense when
    # there's something to pause. We check Stripe directly so we surface
    # truth — not just an assumption based on the env var — in case the
    # operator forgot to run `./manage.py sync_kill_switch` after
    # flipping ANALYTICS_FREE_FOR_ALL. ``None`` = "unknown / no live sub",
    # ``True`` = paused on Stripe, ``False`` = active on Stripe.
    sub_is_paused = _stripe_sub_is_paused(sub) if has_paid_sub else None
    ctx = {
        "subscription": sub,
        "pro_plan": pro,
        "free_for_all": free_for_all,
        "is_pro_active": user_can_access_analytics(request.user),
        "has_paid_sub": has_paid_sub,
        "is_past_due": bool(sub and sub.status == "past_due"),
        "is_canceled": bool(sub and sub.status in ("canceled", "unpaid")),
        "invoices": invoices,
        "sub_is_paused": sub_is_paused,
    }
    return render(request, "portal/billing/index.html", ctx)


def _stripe_sub_is_paused(sub) -> bool | None:
    """True iff Stripe currently has ``pause_collection`` set on the
    subscription. Returns None on transport / lookup failure — the
    template treats None as "unknown" and renders neither banner."""
    if not settings.STRIPE_SECRET_KEY or not sub.stripe_subscription_id:
        return None
    try:
        live = stripe.Subscription.retrieve(sub.stripe_subscription_id)
    except stripe.error.StripeError as exc:
        logger.warning(
            "stripe.Subscription.retrieve(%s) failed: %s",
            sub.stripe_subscription_id, exc,
        )
        return None
    return bool(getattr(live, "pause_collection", None))


def _list_invoices(user) -> list[dict]:
    """Return a flat list of dicts the template can iterate over.

    Stripe errors are caught and logged — we'd rather render the page
    without the history section than 500 the whole billing page. The
    user can always fall back to the Stripe-hosted Customer Portal.
    """
    if not settings.STRIPE_SECRET_KEY:
        return []
    try:
        listing = stripe.Invoice.list(
            customer=user.stripe_customer_id,
            limit=_INVOICE_LIST_LIMIT,
        )
    except stripe.error.StripeError as exc:
        logger.warning(
            "stripe.Invoice.list failed for user %s: %s", user.pk, exc,
        )
        return []
    rows = []
    for inv in listing.data:
        rows.append({
            "number": inv.number or inv.id,
            "created": inv.created,
            "amount_due_cents": inv.amount_due,
            "amount_paid_cents": inv.amount_paid,
            "currency": (inv.currency or "usd").upper(),
            "status": inv.status,  # draft|open|paid|uncollectible|void
            "hosted_invoice_url": inv.hosted_invoice_url or "",
            "invoice_pdf": inv.invoice_pdf or "",
        })
    return rows
