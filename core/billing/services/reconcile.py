"""Daily reconciliation of local subscriptions against Stripe.

The Stripe webhook is the primary state path, but it has one point of failure:
delivery. A missed ``customer.subscription.{updated,deleted}`` leaves the local
status stale — and entitlement gates on status, so a missed cancellation means
lingering PRO access with no safety net. This re-pulls Stripe's canonical state
for every locally-active subscription and re-applies it through the **same
mirror the webhook uses** (``_handle_subscription_event``, idempotent),
correcting any drift. Run daily from ``core.crons.reconcile_subscriptions_cron``.
"""

from __future__ import annotations

import logging

from django.conf import settings

from core.billing.models import Subscription

logger = logging.getLogger(__name__)

# Statuses where a missed webhook would matter: they grant access or are
# mid-lifecycle. ``canceled`` / ``unpaid`` already revoke locally, so there's
# nothing to lose by not re-pulling them (and far more rows to skip).
_RECONCILE_STATUSES = ("trialing", "active", "past_due")


def reconcile_subscriptions() -> dict:
    """Re-pull + re-apply Stripe state for locally-active subs. Returns a
    ``{checked, updated, errors}`` summary; per-sub failures are logged and
    skipped (one bad row never aborts the run)."""
    if not settings.STRIPE_SECRET_KEY:
        logger.info("reconcile_subscriptions: no STRIPE_SECRET_KEY — skipping")
        return {"skipped": True, "checked": 0, "updated": 0, "errors": 0}

    import stripe

    from core.billing import stripe_client  # noqa: F401  (configures the SDK)
    # The canonical "mirror a Stripe subscription into local state" lives next
    # to the webhook that drives it; reuse it so reconcile and webhook can't
    # diverge.
    from core.billing.views.webhook import _handle_subscription_event

    subs = list(
        Subscription.objects
        .filter(status__in=_RECONCILE_STATUSES)
        .exclude(stripe_subscription_id="")
        .select_related("user", "plan")
    )

    checked = updated = errors = 0
    for sub in subs:
        before = (sub.status, sub.current_period_end)
        try:
            stripe_sub = stripe.Subscription.retrieve(sub.stripe_subscription_id)
        except stripe.error.StripeError as exc:
            errors += 1
            logger.warning(
                "reconcile: retrieve %s failed: %s", sub.stripe_subscription_id, exc,
            )
            continue
        try:
            _handle_subscription_event(stripe_sub)
        except Exception:
            errors += 1
            logger.exception("reconcile: apply %s failed", sub.stripe_subscription_id)
            continue

        checked += 1
        sub.refresh_from_db()
        if (sub.status, sub.current_period_end) != before:
            updated += 1
            logger.info(
                "reconcile: %s drifted (status %s → %s)",
                sub.stripe_subscription_id, before[0], sub.status,
            )

    summary = {"checked": checked, "updated": updated, "errors": errors}
    if updated or errors:
        logger.info("reconcile_subscriptions: %s", summary)
    return summary
