"""Billing landing page — current plan + buttons to upgrade / manage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

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
    """
    # Same defensive access as the entitlement helper — never trust the
    # implicit reverse OneToOne, which raises DoesNotExist (not
    # AttributeError) when the row's missing.
    from core.billing.entitlement import _safe_subscription
    sub = _safe_subscription(request.user)
    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    # has_paid_sub = real Stripe subscription (drives invoice list +
    # cancel button visibility).
    has_paid_sub = bool(
        sub
        and sub.stripe_subscription_id
        and sub.plan.features.get("analytics") is True
        and sub.status in ("trialing", "active", "past_due")
    )
    invoices = _list_invoices(request.user) if request.user.stripe_customer_id else []

    # Status filter over the inline (most-recent) list. Older invoices live in
    # the Stripe portal, so a date range adds little here — status only.
    status_filter = request.GET.get("status", "")
    total_invoices = len(invoices)
    _STATUS_MATCH = {
        "paid": lambda s: s == "paid",
        "open": lambda s: s == "open",
        "void": lambda s: s in ("void", "uncollectible"),
    }
    if status_filter in _STATUS_MATCH:
        match = _STATUS_MATCH[status_filter]
        invoices = [i for i in invoices if match(i["status"])]

    ctx = {
        "subscription": sub,
        "pro_plan": pro,
        "is_pro_active": user_can_access_analytics(request.user),
        "has_paid_sub": has_paid_sub,
        "is_past_due": bool(sub and sub.status == "past_due"),
        "is_canceled": bool(sub and sub.status in ("canceled", "unpaid")),
        "invoices": invoices,
        "total_invoices": total_invoices,
        "status_filter": status_filter,
        "invoice_filters": [
            {"label": "All",  "value": "",     "is_active": not status_filter},
            {"label": "Paid", "value": "paid", "is_active": status_filter == "paid"},
            {"label": "Open", "value": "open", "is_active": status_filter == "open"},
            {"label": "Void", "value": "void", "is_active": status_filter == "void"},
        ],
    }
    return render(request, "portal/billing/index.html", ctx)


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
            # Stripe sends `created` as a unix timestamp (int); the usertime
            # filter needs a datetime.
            "created": datetime.fromtimestamp(inv.created, tz=timezone.utc) if inv.created else None,
            "amount_due_cents": inv.amount_due,
            "amount_paid_cents": inv.amount_paid,
            "currency": (inv.currency or "usd").upper(),
            "status": inv.status,  # draft|open|paid|uncollectible|void
            "hosted_invoice_url": inv.hosted_invoice_url or "",
            "invoice_pdf": inv.invoice_pdf or "",
        })
    return rows
