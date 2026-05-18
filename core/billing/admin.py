"""Django admin for the billing app.

Plan: editable so an admin can mint a new tier. The post_save signal
(when wired in the follow-up commit) will push it to Stripe.

Subscription / StripeWebhookEvent: read-only — these are owned by the
Stripe webhook handler. Editing them by hand desyncs us from Stripe.
"""

from __future__ import annotations

from django.contrib import admin

from core.billing.models import Plan, StripeWebhookEvent, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'name', 'amount_cents', 'currency', 'interval',
        'trial_days', 'is_active', 'stripe_price_id',
    )
    search_fields = ('code', 'name', 'stripe_product_id', 'stripe_price_id')
    list_filter = ('is_active', 'interval', 'currency')
    readonly_fields = ('stripe_product_id', 'stripe_price_id', 'created', 'updated')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'plan', 'status', 'current_period_end',
        'cancel_at_period_end', 'stripe_subscription_id',
    )
    search_fields = (
        'user__email', 'user__username',
        'stripe_customer_id', 'stripe_subscription_id',
    )
    list_filter = ('status', 'plan', 'cancel_at_period_end')
    readonly_fields = (
        'user', 'plan', 'status',
        'stripe_customer_id', 'stripe_subscription_id',
        'current_period_start', 'current_period_end',
        'cancel_at_period_end', 'trial_end', 'canceled_at',
        'created', 'updated',
    )

    def has_add_permission(self, request) -> bool:
        # Subscriptions are created by the signup flow + Stripe webhooks,
        # never by hand.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('stripe_event_id', 'event_type', 'received_at', 'processed_at')
    search_fields = ('stripe_event_id', 'event_type')
    list_filter = ('event_type',)
    readonly_fields = (
        'stripe_event_id', 'event_type', 'received_at',
        'processed_at', 'body_excerpt', 'apply_error',
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
