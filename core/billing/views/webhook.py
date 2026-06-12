"""Stripe webhook receiver — single endpoint, multi-event dispatch.

URL: ``/billing/stripe/webhook``. Stripe signs every delivery with
``Stripe-Signature``; we verify via ``stripe.Webhook.construct_event``
(this catches body-rewrites in flight). Idempotency lives in the
``StripeWebhookEvent`` table — redelivery of an already-processed event
short-circuits to a 200 no-op.

Dispatch maps the event type to a handler. Unknown events 200 (so Stripe
stops retrying) but get logged so we notice if a new event type starts
showing up.

See subscription-plan/03-stripe-integration.md §3-4 + 06-user-flows.md
for the full state machine.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any

import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils import timezone as django_tz
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.billing import stripe_client  # noqa: F401
from core.billing.models import Plan, StripeWebhookEvent, Subscription
from core.billing.services import aggrigator_internal
from core.user.models import User

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """Stripe → MDProject inbound. Verify, dedupe, dispatch."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET unset — rejecting all events")
        return HttpResponse(status=503)

    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe.Webhook.construct_event(
            payload=request.body,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("rejecting Stripe webhook: %s", exc)
        return HttpResponse(status=400)

    # Idempotency — INSERT-or-skip. If the row exists, we already
    # processed (or attempted to process) this event id; return 200
    # without re-dispatching.
    _, created = StripeWebhookEvent.objects.get_or_create(
        stripe_event_id=event["id"],
        defaults={
            "event_type": event["type"],
            "body_excerpt": json.dumps(event)[:2000],
        },
    )
    if not created:
        # Re-delivery. If processed_at is null we failed last time and
        # could retry — but we DON'T re-dispatch automatically. Stripe
        # will keep delivering until we 200; we'd rather examine the
        # stale row + retry by hand than loop.
        return HttpResponse(status=200)

    try:
        _dispatch(event)
    except Exception:
        # Record the error, leave processed_at null, return 500 so
        # Stripe retries. The next delivery hits the "already exists"
        # branch and short-circuits — see comment above. Manual retry:
        # delete the StripeWebhookEvent row and replay from Dashboard.
        logger.exception("Stripe webhook apply failed: %s", event["id"])
        StripeWebhookEvent.objects.filter(stripe_event_id=event["id"]).update(
            apply_error=traceback.format_exc()[:8000],
        )
        return HttpResponse(status=500)

    StripeWebhookEvent.objects.filter(stripe_event_id=event["id"]).update(
        processed_at=django_tz.now(),
    )
    return HttpResponse(status=200)


# ---- dispatch table ----------------------------------------------------


def _dispatch(event: dict[str, Any]) -> None:
    et = event["type"]
    obj = event["data"]["object"]
    handler = _HANDLERS.get(et)
    if handler is None:
        logger.info("Stripe webhook %s — no handler, no-op", et)
        return
    handler(obj)


def _handle_checkout_completed(session: dict) -> None:
    """checkout.session.completed — capture stripe_customer_id on the
    User. Subscription state itself arrives via
    customer.subscription.created (which often fires moments earlier or
    later); we don't depend on order here."""
    user = _resolve_user(session)
    if user is None:
        return
    cust_id = session.get("customer", "") or ""
    if cust_id and not user.stripe_customer_id:
        User.objects.filter(pk=user.pk).update(stripe_customer_id=cust_id)
        user.stripe_customer_id = cust_id

    from core.metrics.models import track
    track(user, "checkout_completed", session_id=session.get("id", ""))


def _handle_subscription_event(sub_obj: dict) -> None:
    """customer.subscription.{created,updated,deleted} — single handler.

    Stripe sends the full Subscription object on every event; we just
    upsert from it. Idempotent: re-applying the same values is a no-op
    apart from the ``updated`` timestamp.
    """
    user = _resolve_user(sub_obj)
    if user is None:
        return

    # Pick the plan from the local catalog based on the Stripe price_id.
    # If we can't match (e.g. mid-rollout, before catalog sync), fall
    # back to PRO by code — every paid sub is PRO in v1.
    plan = _resolve_plan(sub_obj)

    status_ = sub_obj.get("status", "")
    sub_id = sub_obj.get("id", "")
    cust_id = sub_obj.get("customer", "") or ""

    period_start = _dt(sub_obj.get("current_period_start"))
    period_end = _dt(sub_obj.get("current_period_end"))
    trial_end = _dt(sub_obj.get("trial_end"))
    canceled_at = _dt(sub_obj.get("canceled_at"))
    cancel_at_period_end = bool(sub_obj.get("cancel_at_period_end", False))

    if status_ == "canceled":
        # Subscription is finally over — downgrade to FREE locally.
        free = Plan.objects.filter(code="FREE", is_active=True).first()
        plan_for_sub = free or plan
    else:
        plan_for_sub = plan

    with transaction.atomic():
        sub, _created = Subscription.objects.get_or_create(
            user=user,
            defaults={
                "plan": plan_for_sub,
                "status": status_ or "active",
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
        sub.status = status_ or sub.status
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

    # Push entitlement to the aggrigator. Map our local state to the
    # tier/status the aggrigator's gate uses (which mirrors Stripe).
    tier = "PRO" if (sub.plan and sub.plan.code == "PRO") else "FREE"
    features = {"analytics": tier == "PRO"}
    try:
        aggrigator_internal.sync_entitlement(
            user, tier=tier, status=sub.status, features=features,
        )
    except aggrigator_internal.ParadiseError as exc:
        # Don't fail the whole webhook on aggrigator hiccup — Stripe
        # will retry the event, and the next attempt will re-sync. We
        # raise so the outer handler records the error.
        raise
    except Exception:
        raise


# ---- helpers -----------------------------------------------------------


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "customer.subscription.created": _handle_subscription_event,
    "customer.subscription.updated": _handle_subscription_event,
    "customer.subscription.deleted": _handle_subscription_event,
    # Informational — we rely on subscription.updated for the state
    # change. invoice.* webhooks DO carry useful UX signals (e.g.
    # invoice.payment_failed → send dunning email) but those are out of
    # scope for v1. Wire them as no-ops so Stripe doesn't keep retrying.
    "invoice.payment_failed": lambda obj: None,
    "invoice.payment_succeeded": lambda obj: None,
    "customer.subscription.trial_will_end": lambda obj: None,
}


def _resolve_user(obj: dict) -> User | None:
    """Find the MDProject User from a Stripe object payload.

    Prefer ``subscription_data.metadata.user_public_id`` (set at Checkout
    time) > ``client_reference_id`` > ``stripe_customer_id`` lookup on
    User. Returns None if all paths fail (we log + move on)."""
    md = (obj.get("metadata") or {})
    public_id = md.get("user_public_id") or obj.get("client_reference_id")
    if public_id:
        u = User.objects.filter(public_id=public_id).first()
        if u is not None:
            return u
    cust_id = obj.get("customer") or ""
    if cust_id:
        u = User.objects.filter(stripe_customer_id=cust_id).first()
        if u is not None:
            return u
    logger.warning(
        "Stripe event could not be resolved to a User: keys=%s", list(obj.keys()),
    )
    return None


def _resolve_plan(sub_obj: dict) -> Plan | None:
    """Map a Stripe Subscription object to the local Plan row.

    Stripe nests price under ``items.data[].price.id``. We pick the
    first non-zero recurring price (v1 is single-line). If that fails,
    fall back to the active PRO plan by code."""
    items = (sub_obj.get("items") or {}).get("data") or []
    if items:
        price_id = (items[0].get("price") or {}).get("id", "")
        if price_id:
            p = Plan.objects.filter(stripe_price_id=price_id).first()
            if p is not None:
                return p
    return Plan.objects.filter(code="PRO", is_active=True).first()


def _dt(unix_ts: int | None) -> datetime | None:
    """Stripe sends timestamps as unix seconds. Convert to aware UTC."""
    if not unix_ts:
        return None
    return datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
