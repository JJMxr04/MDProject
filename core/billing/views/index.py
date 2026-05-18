"""Billing landing page — current plan + buttons to upgrade / manage."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.billing.models import Plan


@login_required(login_url="/auth/login/")
def billing_index(request):
    """Shows the current Subscription state with action buttons.

    - FREE → "Upgrade to PRO" CTA
    - PRO (active/trialing) → "Manage subscription" (Customer Portal link)
    - past_due → grace-period banner + "Update payment method" CTA
    - canceled/unpaid → "Resubscribe" CTA
    """
    sub = getattr(request.user, "subscription", None)
    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    ctx = {
        "subscription": sub,
        "pro_plan": pro,
        # Convenience flags so the template doesn't have to read .status
        # repeatedly. The template still renders defensively for the
        # not-yet-provisioned (sub is None) case.
        "is_pro_active": bool(sub and sub.is_entitled_to_analytics),
        "is_past_due": bool(sub and sub.status == "past_due"),
        "is_canceled": bool(sub and sub.status in ("canceled", "unpaid")),
    }
    return render(request, "portal/billing/index.html", ctx)
