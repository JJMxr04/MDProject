"""Billing — Plan catalog, per-user Subscription, Stripe-event idempotency log.

The catalog (``Plan``) is the source of truth for what we sell; the
``stripe_product_id`` / ``stripe_price_id`` columns are populated when
the catalog-sync signal pushes the row to Stripe (see
``subscription-plan/03-stripe-integration.md`` §2).

A ``Subscription`` exists for every user — FREE-tier rows are local-only
(no Stripe IDs). The status field mirrors Stripe verbatim so the gate
logic on both MDProject and aggrigator uses the same vocabulary.

``StripeWebhookEvent`` is an append-only log keyed by Stripe's event id;
it's how we make Stripe webhook delivery idempotent. Re-delivery of the
same event is detected at ``get_or_create`` time and short-circuited to
a 200 no-op.
"""

from __future__ import annotations

from django.db import models

from core.abstract.models import AbstractModel


class Plan(AbstractModel):
    """Subscription tier definition. One row per plan we sell.

    The FREE plan is a synthetic local-only row (``amount_cents=0``, no
    Stripe IDs) so ``Subscription.plan`` is never null.
    """

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default='usd')
    INTERVAL_CHOICES = [
        ('month', 'month'),
        ('year', 'year'),
    ]
    interval = models.CharField(
        max_length=8, choices=INTERVAL_CHOICES, default='month',
    )
    # 0 = no trial. PRO ships at 7 in v1 — see subscription-plan README.
    trial_days = models.PositiveSmallIntegerField(default=0)
    # Free-form per-tier capability bag. Today: ``{"analytics": true|false}``.
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    # Populated by the post_save signal that pushes the catalog to Stripe.
    # Empty for FREE (local-only) and for plans that haven't synced yet.
    stripe_product_id = models.CharField(max_length=64, blank=True, default='')
    stripe_price_id = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        db_table = 'billing_plan'

    def __str__(self) -> str:
        return f'{self.code} ({self.name})'


class Subscription(AbstractModel):
    """A user's current subscription state.

    Status is the Stripe ``Subscription.status`` verbatim (or ``active``
    for FREE-tier synthetic rows). The grace window for ``past_due`` is
    enforced by ``is_entitled_to_analytics`` so a one-night declined card
    doesn't immediately blank the dashboard.
    """

    STATUS_CHOICES = [
        ('trialing', 'trialing'),
        ('active', 'active'),
        ('past_due', 'past_due'),
        ('unpaid', 'unpaid'),
        ('canceled', 'canceled'),
        ('incomplete', 'incomplete'),
        ('incomplete_expired', 'incomplete_expired'),
    ]

    user = models.OneToOneField(
        'core_user.User',
        on_delete=models.CASCADE,
        related_name='subscription',
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default='active')
    # Stripe IDs — empty when plan is FREE.
    stripe_customer_id = models.CharField(max_length=64, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=64, blank=True, default='')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    trial_end = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'billing_subscription'

    def __str__(self) -> str:
        return f'{self.user.email}: {self.plan.code} ({self.status})'

    @property
    def is_entitled_to_analytics(self) -> bool:
        """True iff the plan grants the PRO feature flag AND status is
        "live enough".

        Grace: ``trialing`` / ``active`` / ``past_due`` keep access. The
        past_due grace exists so Stripe's retry-schedule for a declined
        card doesn't blank a paid surface overnight. ``unpaid`` + ``canceled``
        revoke immediately.

        (Phase 16/D-16d removed the ``ANALYTICS_FREE_FOR_ALL`` kill switch and
        made the analytics dashboard free; this flag now gates opponent
        scouting — Phase 9. The ``analytics`` feature key is retained as the
        PRO marker until generalized to ``is_pro``/``plan.features``.)
        """
        if self.plan.features.get('analytics') is not True:
            return False
        return self.status in ('trialing', 'active', 'past_due')


class StripeWebhookEvent(models.Model):
    """Append-only idempotency log for Stripe webhooks.

    Pattern: INSERT-or-skip keyed by ``stripe_event_id``. On insert, we
    dispatch. On already-exists, we no-op the dispatch and return 200.
    Failure path: dispatch error sets ``apply_error`` + returns 500 so
    Stripe retries; the row is already there but ``processed_at`` is
    null, so the next retry will re-dispatch.
    """

    stripe_event_id = models.CharField(max_length=64, primary_key=True)
    event_type = models.CharField(max_length=64, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    # First ~2k chars of the event body for debugging. Full body is in
    # Stripe Dashboard if we ever need it.
    body_excerpt = models.TextField()
    apply_error = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'billing_stripe_webhook_event'

    def __str__(self) -> str:
        return f'{self.event_type} ({self.stripe_event_id})'
