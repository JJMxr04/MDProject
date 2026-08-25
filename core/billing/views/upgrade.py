"""Upsell page — the redirect target when a FREE user hits a gated route.

Pure render — the actual upgrade button POSTs to ``billing:checkout``,
which creates a Stripe Checkout Session and 303s out to Stripe.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.billing.models import Plan


@login_required(login_url="/auth/login/")
def upgrade_page(request):
    """Show the PRO offer + CTA. Renders an empty-state message if the
    PRO plan isn't seeded yet (admin hasn't created it, or it's marked
    inactive) so the FREE user sees a useful page instead of a 500.
    """
    # A ``src`` marks the upsell surface that sent them here (e.g. the
    # opponent-scouting card) — the click side of the willingness-to-pay
    # funnel (paywall_viewed → paywall_upgrade_clicked).
    src = request.GET.get("src")
    if src:
        from core.metrics.models import track
        track(request.user, "paywall_upgrade_clicked", feature=src)

    from core.billing.entitlement import subscription_pending

    pro = Plan.objects.filter(code="PRO", is_active=True).first()
    sub = getattr(request.user, "subscription", None)
    ctx = {
        "pro_plan": pro,
        "subscription": sub,
        # Show different CTA copy if the user previously had a paid sub
        # (so we don't say "Start free trial" to someone who already
        # consumed theirs).
        "had_prior_paid_sub": _had_prior_paid_sub(request.user),
        # A payer stranded on FREE gets a "refresh" banner instead of being
        # nudged to check out (and pay) a second time.
        "subscription_pending": subscription_pending(request.user),
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
