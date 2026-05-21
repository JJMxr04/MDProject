"""Stripe Customer Portal — invoices, cancel, update payment method.

One Stripe API call → 303 to a Stripe-hosted page where the user does
all post-purchase self-service (view invoices, update card, cancel).
Configure the portal once in the Stripe Dashboard (Settings → Billing
→ Customer Portal); no per-call UI config needed.

A ``flow`` POST param deep-links into a specific Stripe Customer Portal
flow — ``cancel`` opens the cancellation confirmation, ``update_payment``
opens the card-update form. ``manage`` (default) lands on the portal
home. Each ``flow_data`` type must be enabled in Stripe Dashboard →
Settings → Billing → Customer Portal, otherwise Stripe returns an
InvalidRequestError.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

import stripe

from core.billing import stripe_client  # noqa: F401

logger = logging.getLogger(__name__)


_ALLOWED_FLOWS = {"manage", "cancel", "update_payment"}


@login_required(login_url="/auth/login/")
@require_POST
def open_customer_portal(request):
    """Open a Stripe Customer Portal session for the current user.

    Reads the ``flow`` POST param to optionally deep-link into a
    specific flow. Unknown / missing values fall back to ``manage``.
    """
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Billing is not configured.")
        return redirect("core-portal:billing-index")

    user = request.user
    if not user.stripe_customer_id:
        # User clicked "Manage" before they had a Customer record —
        # happens if FREE user lands on the billing page. Redirect to
        # the upgrade page instead.
        return redirect("core-portal:billing-upgrade")

    flow = request.POST.get("flow", "manage")
    if flow not in _ALLOWED_FLOWS:
        flow = "manage"

    return_url = request.build_absolute_uri(reverse("core-portal:billing-index"))
    kwargs: dict = {
        "customer": user.stripe_customer_id,
        "return_url": return_url,
    }
    flow_data = _flow_data_for(flow, user)
    if flow_data is None and flow != "manage":
        # Cancel requested but we don't have a stripe_subscription_id —
        # send them to the generic manage view rather than 500ing.
        messages.warning(
            request,
            "No active subscription found to cancel — opening the billing portal.",
        )
    elif flow_data is not None:
        kwargs["flow_data"] = flow_data

    try:
        session = stripe.billing_portal.Session.create(**kwargs)
    except stripe.error.StripeError as exc:
        logger.exception("Customer Portal session create failed (flow=%s)", flow)
        messages.error(
            request, f"Couldn't open billing portal: {exc.user_message or 'try again'}",
        )
        return redirect("core-portal:billing-index")

    return HttpResponseRedirect(session.url)


def _flow_data_for(flow: str, user) -> dict | None:
    """Map our short flow name to Stripe's ``flow_data`` payload.

    Returns ``None`` for ``manage`` (no flow_data → portal home) and
    for ``cancel`` when the user has no Stripe subscription id on file
    (so the caller can fall back to manage instead of erroring).
    """
    if flow == "update_payment":
        return {"type": "payment_method_update"}
    if flow == "cancel":
        sub_id = getattr(getattr(user, "subscription", None), "stripe_subscription_id", "")
        if not sub_id:
            return None
        return {
            "type": "subscription_cancel",
            "subscription_cancel": {"subscription": sub_id},
        }
    return None
