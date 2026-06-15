"""Stripe webhook idempotency + the redelivery-reprocesses-failures fix.

``construct_event`` is mocked (no real signature), and ``_dispatch`` is mocked
so we can drive success/failure and count (re)dispatches.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.billing.models import Plan, StripeWebhookEvent
from core.match.tests.factories import make_user

_EVENT = {
    "id": "evt_1",
    "type": "customer.subscription.updated",
    "data": {"object": {"id": "sub_1", "status": "active"}},
}

_SYNC = "core.billing.services.aggrigator_internal.sync_entitlement"


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test")
class WebhookRedeliveryTests(TestCase):
    def setUp(self):
        self.url = reverse("billing-stripe-webhook")

    def _post(self):
        return self.client.post(
            self.url, data="{}", content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=x",
        )

    def test_processed_event_is_skipped_on_redelivery(self):
        with mock.patch("stripe.Webhook.construct_event", return_value=_EVENT), \
                mock.patch("core.billing.views.webhook._dispatch") as dispatch:
            r1 = self._post()
            r2 = self._post()  # exact redelivery
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        dispatch.assert_called_once()  # second delivery short-circuits
        evt = StripeWebhookEvent.objects.get(stripe_event_id="evt_1")
        self.assertIsNotNone(evt.processed_at)

    def test_failed_event_is_reprocessed_on_redelivery(self):
        with mock.patch("stripe.Webhook.construct_event", return_value=_EVENT), \
                mock.patch(
                    "core.billing.views.webhook._dispatch",
                    side_effect=[Exception("boom"), None],
                ) as dispatch:
            r1 = self._post()   # dispatch raises -> 500, processed_at stays null
            r2 = self._post()   # redelivery of a FAILED event -> re-dispatch
        self.assertEqual(r1.status_code, 500)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(dispatch.call_count, 2)  # reprocessed, not skipped
        evt = StripeWebhookEvent.objects.get(stripe_event_id="evt_1")
        self.assertIsNotNone(evt.processed_at)  # now succeeded

    def test_first_delivery_dispatches_and_marks_processed(self):
        with mock.patch("stripe.Webhook.construct_event", return_value=_EVENT), \
                mock.patch("core.billing.views.webhook._dispatch") as dispatch:
            r = self._post()
        self.assertEqual(r.status_code, 200)
        dispatch.assert_called_once()
        self.assertEqual(StripeWebhookEvent.objects.count(), 1)

    def test_missing_webhook_secret_503(self):
        with override_settings(STRIPE_WEBHOOK_SECRET=""):
            r = self._post()
        self.assertEqual(r.status_code, 503)


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test", STRIPE_SECRET_KEY="sk_test")
class CheckoutStaleCustomerIdTests(TestCase):
    """checkout.session.completed overwrites a *stale* ``stripe_customer_id``
    on the User. The end-to-end FREE→PRO fulfilment is covered by
    ``tests_webhook_fulfillment.py``; this guards the narrower fix that the
    authoritative checkout points the User at the customer it just paid under —
    otherwise self-serve refresh + the customer portal (both list subs by
    ``user.stripe_customer_id``) would target the orphan and re-strand them."""

    def setUp(self):
        self.url = reverse("billing-stripe-webhook")
        self.user = make_user("payer")
        self.user.stripe_customer_id = "cus_STALE"
        self.user.save(update_fields=["stripe_customer_id"])
        Plan.objects.create(
            code="FREE", name="Free", amount_cents=0,
            features={"analytics": False}, is_active=True,
        )
        Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900, features={"analytics": True},
            stripe_price_id="price_1", is_active=True,
        )

    @mock.patch(_SYNC)
    def test_stale_customer_id_is_overwritten(self, _sync):
        event = {
            "id": "evt_checkout_1",
            "type": "checkout.session.completed",
            "data": {"object": {
                "id": "cs_1", "mode": "subscription",
                "customer": "cus_NEW", "subscription": "sub_NEW",
                "client_reference_id": str(self.user.public_id),
            }},
        }
        retrieved = {
            "id": "sub_NEW", "status": "active", "customer": "cus_NEW",
            "items": {"data": [{"price": {"id": "price_1"}}]},
            "current_period_start": 1_900_000_000,
            "current_period_end": 2_000_000_000,
        }
        with mock.patch("stripe.Webhook.construct_event", return_value=event), \
                mock.patch("stripe.Subscription.retrieve", return_value=retrieved):
            r = self.client.post(
                self.url, data="{}", content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=x",
            )
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.stripe_customer_id, "cus_NEW")
