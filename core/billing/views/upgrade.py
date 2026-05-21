"""Upsell page — the redirect target when a FREE user hits a gated route.

Pure render — the actual upgrade button POSTs to ``billing:checkout``,
which creates a Stripe Checkout Session and 303s out to Stripe.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.billing.models import Plan


@login_required(login_url="/auth/login/")
def upgrade_page(request):
    """Show the PRO offer + CTA. Renders an empty-state message if the
    PRO plan isn't seeded yet (admin hasn't created it, or it's marked
    inactive) so the FREE user sees a useful page instead of a 500.

    When ``ANALYTICS_FREE_FOR_ALL`` is on there's nothing to upgrade to,
    so we bounce to the billing landing page (which shows the free-mode
    banner instead).
    """
    if getattr(settings, "ANALYTICS_FREE_FOR_ALL", False):
        return redirect("core-portal:billing-index")
    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    sub = getattr(request.user, "subscription", None)
    ctx = {
        "pro_plan": pro,
        "subscription": sub,
        # Show different CTA copy if the user previously had a paid sub
        # (so we don't say "Start free trial" to someone who already
        # consumed theirs — file 06 §5).
        "had_prior_paid_sub": _had_prior_paid_sub(request.user),
    }
    return render(request, "portal/billing/upgrade.html", ctx)


def _had_prior_paid_sub(user) -> bool:
    """True iff the user has ever been on a non-FREE plan (any status
    except the never-actually-started ``incomplete*`` states). Used to
    suppress the trial on re-subscribe (Stripe-side enforcement happens
    in start_checkout)."""
    from core.billing.models import Subscription
    return Subscription.objects.filter(
        user=user, plan__code="PRO",
    ).exclude(status__in=("incomplete", "incomplete_expired")).exists()
