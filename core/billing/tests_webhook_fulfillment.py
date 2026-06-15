"""Webhook fulfillment: a paid checkout must actually entitle the user.

These exercise the REAL handler chain (resolve -> upsert Subscription ->
sync_entitlement), unlike tests_webhook.py which mocks _dispatch. They cover
the regression where a user paid but stayed on their default FREE row because
entitlement hung solely off customer.subscription.* resolution: checkout.session
.completed now applies the subscription authoritatively via client_reference_id.

Only the boundaries are mocked: signature verification, the outbound aggrigator
HTTP call, and (for the checkout path) stripe.Subscription.retrieve. The signup
aggrigator provisioning is mocked too so the FREE row is created without a
network call.
"""

from __future__ import annotations

from contextlib import ExitStack
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.billing.entitlement import user_can_access_analytics
from core.billing.models import Plan, Subscription
from core.match.tests.factories import make_user


def _subscription_payload(user, *, status="active", price_id="price_123"):
    """Shape of a Stripe Subscription object as our handler reads it."""
    return {
        "id": "sub_test_1",
        "status": status,
        "customer": "cus_test_1",
        "metadata": {"user_public_id": str(user.public_id)},
        "items": {"data": [{"price": {"id": price_id}}]},
        "current_period_start": 1_700_000_000,
        "current_period_end": 1_702_000_000,
        "cancel_at_period_end": False,
    }


@override_settings(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="whsec_test")
class WebhookFulfillmentTests(TestCase):
    def setUp(self):
        # Mock signup-time aggrigator provisioning so make_user() still gets
        # its FREE Subscription row but does no network I/O.
        patcher = mock.patch(
            "core.billing.services.aggrigator_internal.provision_user",
            return_value="",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        # FREE must exist before the user is created: the signup signal gives
        # every user a FREE Subscription row, and prod entitlement is the
        # FREE-row-flipped-to-PRO path, not a fresh insert.
        self.free = Plan.objects.create(
            code="FREE", name="Free", amount_cents=0,
            features={"analytics": False}, is_active=True,
        )
        self.pro = Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900,
            features={"analytics": True}, stripe_price_id="price_123",
            is_active=True,
        )
        self.user = make_user("buyer")
        self.url = reverse("billing-stripe-webhook")

    def _post_event(self, event, *, retrieve=None):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch("stripe.Webhook.construct_event", return_value=event))
            stack.enter_context(mock.patch(
                "core.billing.views.webhook.aggrigator_internal.sync_entitlement"))
            if retrieve is not None:
                stack.enter_context(
                    mock.patch("stripe.Subscription.retrieve", return_value=retrieve))
            return self.client.post(
                self.url, data="{}", content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=x",
            )

    def test_user_starts_on_free(self):
        # Precondition: signup left them on a non-entitled FREE row.
        self.assertFalse(user_can_access_analytics(self.user))

    def test_checkout_completed_entitles_user_without_subscription_event(self):
        """The regression: even if customer.subscription.* never resolves, a
        completed checkout alone must upgrade the user to PRO — and it resolves
        on client_reference_id, so a stale/missing customer-id can't block it."""
        sub = _subscription_payload(self.user, status="active")
        event = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_1",
                "mode": "subscription",
                "customer": "cus_stale_mismatch",
                "subscription": "sub_test_1",
                "client_reference_id": str(self.user.public_id),
            }},
        }
        resp = self._post_event(event, retrieve=sub)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(
            user_can_access_analytics(self.user),
            "completed checkout did not entitle the user",
        )
        row = Subscription.objects.get(user=self.user)
        self.assertEqual(row.plan.code, "PRO")
        self.assertEqual(row.status, "active")

    def test_non_subscription_checkout_does_not_call_stripe(self):
        """A one-off (mode=payment) checkout has no subscription to apply."""
        event = {
            "id": "evt_checkout_payment",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_test_2",
                "mode": "payment",
                "customer": "cus_x",
                "client_reference_id": str(self.user.public_id),
            }},
        }
        with mock.patch("stripe.Subscription.retrieve") as retrieve:
            resp = self._post_event(event)
        self.assertEqual(resp.status_code, 200)
        retrieve.assert_not_called()
        self.assertFalse(user_can_access_analytics(self.user))

    def test_subscription_created_event_entitles_user(self):
        event = {
            "id": "evt_sub_1",
            "type": "customer.subscription.created",
            "data": {"object": _subscription_payload(self.user, status="active")},
        }
        resp = self._post_event(event)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(user_can_access_analytics(self.user))

    def test_trialing_status_is_entitled(self):
        event = {
            "id": "evt_sub_trial",
            "type": "customer.subscription.created",
            "data": {"object": _subscription_payload(self.user, status="trialing")},
        }
        resp = self._post_event(event)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(user_can_access_analytics(self.user))
