"""Admin-triggered re-sync of a single User's subscription state.

The Stripe webhook handler in ``core/billing/views/webhook.py`` is the
normal source of truth for ``Subscription`` rows. This module exists
for the admin "Refresh subscription" button: an operator who suspects
the local row drifted (lost webhook, manual Dashboard change, restored
from backup) can re-pull the live state from Stripe in one click.

Single entry point: ``refresh_from_stripe(user)``. It:

1. Lists Stripe Subscriptions for ``user.stripe_customer_id`` (most
   recently created first) and picks the first non-canceled one. If
   every Stripe-side sub is canceled, the most-recent canceled wins
   so the local row reflects "user once paid, now ended".
2. Upserts the local ``Subscription`` row from that payload — same
   field mapping the webhook handler uses.
3. Pushes the resulting tier/status to the aggrigator via
   ``sync_entitlement`` so the gate on both sides agrees.

Failure modes are surfaced via ``SubscriptionSyncError`` so the admin
view can pass ``user_message`` straight to Django's messages
framework."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import stripe
from django.db import transaction

# Side-effect import — wires our Stripe API key + pinned version.
from core.billing import stripe_client  # noqa: F401
from core.billing.models import Plan, Subscription
from core.billing.services import aggrigator_internal

logger = logging.getLogger(__name__)


class SubscriptionSyncError(Exception):
    """Refresh failed. ``user_message`` is safe to surface in admin."""

    def __init__(self, message: str, *, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


@dataclass(frozen=True)
class SyncReport:
    """Per-user outcome of the refresh — used by the admin handler to
    render a clear success message."""
    found_on_stripe: bool
    stripe_subscription_id: str
    status: str
    plan_code: str
    aggrigator_synced: bool


def refresh_from_stripe(user) -> SyncReport:
    """Pull live Stripe Subscription state and re-apply it locally + on
    the aggrigator. Returns a ``SyncReport`` describing what happened.

    Raises ``SubscriptionSyncError`` on:
    - missing ``stripe_customer_id`` (nothing to refresh from)
    - Stripe transport / auth failures
    - aggrigator HMAC / network errors (after the local row is already
      written; caller can still report partial success via the report's
      ``aggrigator_synced`` flag).
    """
    if not user.stripe_customer_id:
        raise SubscriptionSyncError(
            "User has no stripe_customer_id — create a Customer first "
            "(Reconnect or Create-new buttons) before refreshing.",
            user_message=(
                "No Stripe Customer linked. Use Reconnect / Create-new "
                "Stripe customer first."
            ),
        )

    try:
        listing = stripe.Subscription.list(
            customer=user.stripe_customer_id,
            status="all",
            limit=10,
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.Subscription.list failed for user_id=%s", user.pk)
        raise SubscriptionSyncError(
            f"Stripe Subscription.list failed: {exc}",
            user_message=getattr(exc, "user_message", None) or str(exc),
        ) from exc

    subs = list(listing.auto_paging_iter()) if hasattr(
        listing, "auto_paging_iter",
    ) else list(listing.get("data", []))

    if not subs:
        # No subscription history at all on Stripe. Force the local row
        # back to FREE so the gate matches reality.
        _apply_free(user)
        _push_entitlement(user, tier="FREE", status="active")
        return SyncReport(
            found_on_stripe=False,
            stripe_subscription_id="",
            status="active",
            plan_code="FREE",
            aggrigator_synced=True,
        )

    # Prefer the first non-canceled sub (Stripe returns newest-first by
    # default). If everything is canceled we still want to mirror the
    # most-recent canceled sub so the local row shows the right end-state.
    live = next(
        (s for s in subs if s.get("status") and s["status"] != "canceled"),
        subs[0],
    )

    plan = _apply_subscription(user, live)

    tier = "PRO" if (plan and plan.code == "PRO") else "FREE"
    agg_ok = _push_entitlement(user, tier=tier, status=live.get("status") or "active")

    return SyncReport(
        found_on_stripe=True,
        stripe_subscription_id=live.get("id") or "",
        status=live.get("status") or "",
        plan_code=plan.code if plan else "",
        aggrigator_synced=agg_ok,
    )


# ---- internals -------------------------------------------------------------


def _apply_subscription(user, sub_obj: dict) -> Plan | None:
    """Upsert the local Subscription row from a Stripe payload. Mirrors
    the webhook handler's field mapping (intentionally — they're the
    same operation triggered from different sources)."""
    plan = _resolve_plan(sub_obj)
    status_ = sub_obj.get("status") or "active"
    sub_id = sub_obj.get("id") or ""
    cust_id = sub_obj.get("customer") or user.stripe_customer_id

    period_start = _dt(sub_obj.get("current_period_start"))
    period_end = _dt(sub_obj.get("current_period_end"))
    trial_end = _dt(sub_obj.get("trial_end"))
    canceled_at = _dt(sub_obj.get("canceled_at"))
    cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))

    if status_ == "canceled":
        free = Plan.objects.filter(code="FREE", is_active=True).first()
        plan_for_sub = free or plan
    else:
        plan_for_sub = plan

    if plan_for_sub is None:
        raise SubscriptionSyncError(
            "No matching local Plan row — seed the catalog (FREE + PRO) "
            "before refreshing subscriptions.",
            user_message=(
                "No local Plan to attach. Seed FREE / PRO via the Plan "
                "admin before refreshing."
            ),
        )

    with transaction.atomic():
        sub, _created = Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": plan_for_sub,
                "status": status_,
                "stripe_customer_id": cust_id,
                "stripe_subscription_id": sub_id,
                "current_period_start": period_start,
                "current_period_end": period_end,
                "trial_end": trial_end,
                "cancel_at_period_end": cancel_at_period_end,
                "canceled_at": canceled_at,
            },
        )
        sub.plan = plan_for_sub
        sub.status = status_
        if cust_id:
            sub.stripe_customer_id = cust_id
        if sub_id:
            sub.stripe_subscription_id = sub_id
        sub.current_period_start = period_start
        sub.current_period_end = period_end
        sub.trial_end = trial_end
        sub.cancel_at_period_end = cancel_at_period_end
        sub.canceled_at = canceled_at
        sub.save()

    return plan_for_sub


def _apply_free(user) -> None:
    """No Stripe history → reset the local Subscription to FREE."""
    free = Plan.objects.filter(code="FREE", is_active=True).first()
    if free is None:
        raise SubscriptionSyncError(
            "No active FREE Plan row — seed one before refreshing.",
            user_message="Seed an active FREE Plan before refreshing.",
        )
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": free,
            "status": "active",
            "stripe_subscription_id": "",
            "current_period_start": None,
            "current_period_end": None,
            "trial_end": None,
            "cancel_at_period_end": False,
            "canceled_at": None,
        },
    )


def _push_entitlement(user, *, tier: str, status: str) -> bool:
    """Best-effort aggrigator sync. Returns False on aggrigator failure
    so the admin handler can surface a partial-success message instead
    of unwinding the local-write."""
    try:
        aggrigator_internal.sync_entitlement(
            user, tier=tier, status=status,
            features={"analytics": tier == "PRO"},
        )
    except aggrigator_internal.ParadiseError as exc:
        logger.warning(
            "aggrigator sync_entitlement failed for user_id=%s — %s",
            user.pk, exc,
        )
        return False
    return True


def _resolve_plan(sub_obj: dict) -> Plan | None:
    items = (sub_obj.get("items") or {}).get("data") or []
    if items:
        price_id = (items[0].get("price") or {}).get("id", "")
        if price_id:
            p = Plan.objects.filter(stripe_price_id=price_id).first()
            if p is not None:
                return p
    return Plan.objects.filter(code="PRO", is_active=True).first()


def _dt(unix_ts: int | None) -> datetime | None:
    if not unix_ts:
        return None
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
