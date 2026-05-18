"""Billing signal handlers.

Wired in via ``BillingConfig.ready()``.

1. **User post_save (created)** — provision a TenantUser in the aggrigator
   and create a FREE Subscription row. Failures here are non-fatal: the
   user still exists; the next analytics page hit (defensive call in
   ``@require_paid``) or a re-run of the backfill script will catch them.
   See subscription-plan/04-internal-api.md §7a.

2. **Plan post_save** — push the catalog row to Stripe (Product +
   Price). Empty stub here; the catalog sync ships in a follow-up
   commit alongside the stripe-python install. See file 03 §2.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.billing.models import Plan, Subscription
from core.billing.services import aggrigator_internal
from core.user.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def provision_aggrigator_on_signup(sender, instance, created, **kwargs):
    """First post_save fire on a User — mirror them into the aggrigator
    and give them a FREE Subscription row.

    Side-effect order is deliberate:
    1. Create local Subscription first (cheap, transactional with the
       user-create transaction).
    2. THEN call the aggrigator. If the aggrigator is down, the user
       still has a working FREE row locally; provisioning catches up via
       the backfill script or the @require_paid safety net.
    """
    if not created:
        return  # only fire on the original INSERT, not subsequent updates

    # Local Subscription row — every user has one, FREE-tier rows are
    # local-only (no Stripe IDs).
    try:
        free = Plan.objects.filter(code='FREE', is_active=True).first()
        if free is not None:
            Subscription.objects.get_or_create(
                user=instance,
                defaults={'plan': free, 'status': 'active'},
            )
        else:
            logger.warning(
                'No active FREE Plan row found — user %s has no '
                'Subscription. Seed FREE via Django admin or shell.',
                instance.pk,
            )
    except Exception:
        # NEVER crash the signup transaction over a Subscription row.
        # Worst case the user shows up with no Subscription, the
        # @require_paid decorator's "sub is None" branch will redirect
        # them to /billing/upgrade/.
        logger.exception('failed to create FREE Subscription for %s', instance.pk)

    # Aggrigator mirror — only if integration is enabled.
    if not getattr(settings, 'USE_AGGRIGATOR', False):
        return
    if instance.aggrigator_api_key:
        # Already provisioned (e.g. user object hot-reloaded after a
        # backfill run). Don't re-mint a key.
        return

    try:
        key = aggrigator_internal.provision_user(instance, tier='FREE')
    except Exception:
        logger.exception(
            'aggrigator provisioning failed for user %s — will retry via '
            'backfill script or @require_paid safety net',
            instance.pk,
        )
        return

    # Only update if we got a fresh key back (201). 200 (already exists)
    # returns empty string; in that case MDProject's record is the stale
    # one and the operator should re-key via rotate_api_key.
    if key:
        User.objects.filter(pk=instance.pk).update(
            aggrigator_api_key=key,
            aggrigator_external_id=instance.public_id,
        )
        # Refresh in-memory instance so downstream signal handlers see
        # the new values without a round-trip.
        instance.aggrigator_api_key = key
        instance.aggrigator_external_id = instance.public_id


@receiver(post_save, sender=Plan)
def sync_plan_to_stripe_handler(sender, instance, **kwargs):
    """Push the catalog row to Stripe whenever it's saved.

    Idempotent — re-saving with no changes is a no-op on the Stripe side
    (Product.modify with same values, Price not touched).
    Skipped entirely for FREE (local-only).

    Failures are logged + swallowed: a Stripe outage shouldn't block an
    admin from saving a Plan row. Re-save when Stripe is back to retry.
    """
    if instance.code == 'FREE':
        return
    if not getattr(settings, 'STRIPE_SECRET_KEY', ''):
        # Dev without Stripe credentials configured — silently skip
        # rather than spamming the logs on every save.
        return
    try:
        from core.billing.services.catalog import sync_plan_to_stripe
        sync_plan_to_stripe(instance)
    except Exception:
        logger.exception(
            'Stripe catalog sync failed for plan %s — re-save to retry',
            instance.code,
        )
