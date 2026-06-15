"""Self-serve "refresh my subscription".

A user-facing wrapper around ``subscription_sync.refresh_from_stripe`` (the
same re-pull the admin "Refresh subscription" button uses). It exists so a
payer who got stranded on FREE — the FREE→PRO webhook resolved to None and
200'd — can recover without an operator, instead of being shown a pay-again
CTA they'd double-charge themselves on. See
``core/billing/views/webhook.py`` for the stranding mechanism this heals.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.billing.services.subscription_sync import (
    SubscriptionSyncError,
    refresh_from_stripe,
)


@login_required(login_url="/auth/login/")
@require_POST
def refresh_subscription(request):
    """Re-pull live Stripe state, re-apply it locally + to the aggrigator,
    then redirect back to where the user was with a result message."""
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        next_url = reverse("core-portal:billing-upgrade")

    try:
        report = refresh_from_stripe(request.user)
    except SubscriptionSyncError as exc:
        messages.warning(request, exc.user_message)
        return redirect(next_url)

    if report.found_on_stripe and report.plan_code == "PRO":
        messages.success(
            request, "Your PRO subscription is now active — thanks for your patience!",
        )
    else:
        messages.info(
            request,
            "We couldn't find an active subscription on file. If you just "
            "checked out, give it a moment and try again, or contact support.",
        )
    return redirect(next_url)
