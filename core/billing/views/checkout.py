"""Stripe Checkout Session creation + the post-checkout thanks page.

The redirect-out-to-Stripe pattern: we never see a card. User clicks
"Subscribe" → we create a Checkout Session via Stripe API → 303 to the
session URL (Stripe-hosted). Stripe handles the payment UI. On success
Stripe redirects back to our ``success_url`` + fires webhooks.
"""

from __future__ import annotations

import logging
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import stripe

# Configure stripe SDK at module import.
from core.billing import stripe_client  # noqa: F401
from core.billing.models import Plan, Subscription

logger = logging.getLogger(__name__)


@login_required(login_url="/auth/login/")
@require_POST
def start_checkout(request):
    """Mint a Stripe Checkout Session for PRO and redirect the browser."""
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Billing is not configured. Contact support.")
        return redirect("core-portal:billing-upgrade")

    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    if pro is None or not pro.stripe_price_id:
        logger.error(
            "checkout requested but PRO plan or its Stripe price is missing"
        )
        messages.error(request, "PRO plan is not available right now.")
        return redirect("core-portal:billing-upgrade")

    user = request.user

    # Re-subscribers don't get a fresh trial (file 06 §5). Stripe-side
    # enforcement: we just omit trial_period_days when they've had a
    # paid sub before.
    prior_paid = Subscription.objects.filter(
        user=user, plan__code="PRO",
    ).exclude(status__in=("incomplete", "incomplete_expired")).exists()
    trial_days = 0 if prior_paid else (pro.trial_days or 0)

    # Reuse the Stripe Customer if we have one; else let Stripe create
    # one in the session and we'll capture it on the
    # checkout.session.completed webhook. NB: ``customer_creation`` is
    # only valid in ``mode=payment`` — in ``mode=subscription`` Stripe
    # auto-creates a Customer when one isn't passed, so we only pass
    # ``customer_email`` (prefills the form).
    customer_kwargs: dict = {}
    if user.stripe_customer_id:
        customer_kwargs["customer"] = user.stripe_customer_id
    else:
        customer_kwargs["customer_email"] = user.email

    success_url = request.build_absolute_uri(
        reverse("core-portal:billing-thanks")
        + "?session_id={CHECKOUT_SESSION_ID}"
    )
    cancel_url = request.build_absolute_uri(
        reverse("core-portal:billing-upgrade")
    )

    subscription_data: dict = {
        "metadata": {"user_public_id": str(user.public_id)},
    }
    if trial_days > 0:
        subscription_data["trial_period_days"] = trial_days

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": pro.stripe_price_id, "quantity": 1}],
            subscription_data=subscription_data,
            # Two independent ways to recover the user from a Stripe
            # event payload, in case Stripe changes shape on one of them
            # (defensive — costs nothing to send both).
            client_reference_id=str(user.public_id),
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True,
            # Bucket per-minute so a double-click returns the same
            # session instead of two parallel ones.
            idempotency_key=f"checkout-{user.public_id}-{int(time.time()) // 60}",
            **customer_kwargs,
        )
    except stripe.error.StripeError as exc:
        logger.exception("Stripe Checkout Session create failed")
        messages.error(request, f"Checkout failed: {exc.user_message or 'try again'}")
        return redirect("core-portal:billing-upgrade")

    return HttpResponseRedirect(session.url)


@login_required(login_url="/auth/login/")
def checkout_thanks(request):
    """Landing page after a successful Checkout. The subscription state
    isn't necessarily synced yet — Stripe fires the webhook within a few
    seconds, but the user might land here first. Template shows a
    "you're all set, check back in a moment" message and a link to
    /web/portal/analytics/."""
    session_id = request.GET.get("session_id", "")
    return render(request, "portal/billing/thanks.html", {
        "session_id": session_id,
    })
