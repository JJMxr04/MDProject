"""Stripe webhook idempotency + the redelivery-reprocesses-failures fix.

``construct_event`` is mocked (no real signature), and ``_dispatch`` is mocked
so we can drive success/failure and count (re)dispatches.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.billing.models import StripeWebhookEvent

_EVENT = {
    "id": "evt_1",
    "type": "customer.subscription.updated",
    "data": {"object": {"id": "sub_1", "status": "active"}},
}


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
