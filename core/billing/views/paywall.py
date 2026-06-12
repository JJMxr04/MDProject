"""Fake-paywall interstitial (roadmap Phase 3 §4, decisions D-3/D-10).

While ``ANALYTICS_FREE_FOR_ALL`` is on, testers without a real PRO sub
hit this wall once per session on their way into a gated analytics view:
they see the displayed price, can click Upgrade (a real Stripe TEST
checkout), or continue for free. Every impression and click lands in
``ProductEvent`` — the view→click rate is the willingness-to-pay signal
that prices PRO later (decision D-10).

The redirect into this page lives in ``core.billing.decorators
.require_paid``; the wall only exists when BOTH ``FAKE_PAYWALL_ENABLED``
and ``ANALYTICS_FREE_FOR_ALL`` are on.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.billing.models import Plan
from core.metrics.models import track

# Session key marking "this user has seen + dismissed the wall" — checked
# by @require_paid so the interstitial shows once per session, not per view.
PAYWALL_ACK_SESSION_KEY = "fake_paywall_ack"


def _safe_next(request) -> str:
    candidate = request.GET.get("next") or request.POST.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse("core-portal:portal-dashboard")


@login_required(login_url="/auth/login/")
def paywall_interstitial(request):
    """Render the wall + record the impression."""
    if not (
        getattr(settings, "FAKE_PAYWALL_ENABLED", False)
        and getattr(settings, "ANALYTICS_FREE_FOR_ALL", False)
    ):
        return redirect("core-portal:billing-index")

    next_url = _safe_next(request)
    track(request.user, "paywall_viewed",
          next=next_url, price=settings.PAYWALL_DISPLAY_PRICE)
    return render(request, "portal/billing/paywall.html", {
        "display_price": settings.PAYWALL_DISPLAY_PRICE,
        "pro_plan": Plan.objects.filter(code="PRO", is_active=True).first(),
        "next_url": next_url,
    })


@login_required(login_url="/auth/login/")
@require_POST
def paywall_continue(request):
    """\"Not now\" — let the tester through and stop walling this session.
    No event on purpose: dismissals = paywall_viewed − paywall_upgrade_clicked."""
    request.session[PAYWALL_ACK_SESSION_KEY] = True
    return redirect(_safe_next(request))
