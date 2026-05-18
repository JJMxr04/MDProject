"""Stripe Customer Portal — invoices, cancel, update payment method.

One Stripe API call → 303 to a Stripe-hosted page where the user does
all post-purchase self-service (view invoices, update card, cancel).
Configure the portal once in the Stripe Dashboard (Settings → Billing
→ Customer Portal); no per-call UI config needed.
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


@login_required(login_url="/auth/login/")
@require_POST
def open_customer_portal(request):
    """Open a Stripe Customer Portal session for the current user."""
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Billing is not configured.")
        return redirect("core-portal:billing-index")

    user = request.user
    if not user.stripe_customer_id:
        # User clicked "Manage" before they had a Customer record —
        # happens if FREE user lands on the billing page. Redirect to
        # the upgrade page instead.
        return redirect("core-portal:billing-upgrade")

    try:
        session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=request.build_absolute_uri(
                reverse("core-portal:billing-index")
            ),
        )
    except stripe.error.StripeError as exc:
        logger.exception("Customer Portal session create failed")
        messages.error(
            request, f"Couldn't open billing portal: {exc.user_message or 'try again'}",
        )
        return redirect("core-portal:billing-index")

    return HttpResponseRedirect(session.url)
