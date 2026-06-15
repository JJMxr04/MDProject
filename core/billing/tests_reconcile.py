"""Daily subscription reconcile (safety net for missed Stripe webhooks).

Plans are created with ``STRIPE_SECRET_KEY=""`` (no catalog push); the key is
overridden only around the reconcile call. The aggregator entitlement sync is
patched out so the local-mirror assertions don't depend on a live aggregator.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

from django.test import TestCase, override_settings

from core.billing.models import Plan, Subscription
from core.billing.services.reconcile import reconcile_subscriptions
from core.match.tests.factories import make_user

_KEY = "sk_test_dummy"
_PERIOD_END_TS = 2_000_000_000
_PERIOD_END = datetime.fromtimestamp(_PERIOD_END_TS, tz=timezone.utc)
_SYNC = "core.billing.services.aggrigator_internal.sync_entitlement"


@override_settings(STRIPE_SECRET_KEY="")
class ReconcileSubscriptionsTests(TestCase):
    def setUp(self):
        self.user = make_user("sub")
        self.user.stripe_customer_id = "cus_1"
        self.user.save(update_fields=["stripe_customer_id"])
        self.pro = Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900,
            features={"analytics": True}, stripe_price_id="price_1", is_active=True,
        )
        self.free = Plan.objects.create(
            code="FREE", name="Free", amount_cents=0,
            features={"analytics": False}, is_active=True,
        )
        self.sub = Subscription.objects.create(
            user=self.user, plan=self.pro, status="active",
            stripe_subscription_id="sub_1", stripe_customer_id="cus_1",
            current_period_end=_PERIOD_END,
        )

    def _stripe_sub(self, status):
        return {
            "id": "sub_1",
            "status": status,
            "customer": "cus_1",
            "metadata": {"user_public_id": str(self.user.public_id)},
            "items": {"data": [{"price": {"id": "price_1"}}]},
            "current_period_start": 1_900_000_000,
            "current_period_end": _PERIOD_END_TS,
            "cancel_at_period_end": False,
            "canceled_at": (_PERIOD_END_TS if status == "canceled" else None),
            "trial_end": None,
        }

    @mock.patch(_SYNC)
    def test_drift_to_canceled_is_corrected(self, _sync):
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.Subscription.retrieve", return_value=self._stripe_sub("canceled")):
            summary = reconcile_subscriptions()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "canceled")
        self.assertEqual(self.sub.plan.code, "FREE")  # canceled downgrades plan
        self.assertEqual(summary["updated"], 1)
        self.assertEqual(summary["errors"], 0)

    @mock.patch(_SYNC)
    def test_no_drift_no_update(self, _sync):
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.Subscription.retrieve", return_value=self._stripe_sub("active")):
            summary = reconcile_subscriptions()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")
        self.assertEqual(summary, {"checked": 1, "updated": 0, "errors": 0})

    def test_no_stripe_key_skips(self):
        with mock.patch("stripe.Subscription.retrieve") as retrieve:
            summary = reconcile_subscriptions()  # key is "" from class override
        retrieve.assert_not_called()
        self.assertTrue(summary["skipped"])

    @mock.patch(_SYNC)
    def test_retrieve_error_is_counted_not_fatal(self, _sync):
        import stripe
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.Subscription.retrieve", side_effect=stripe.error.StripeError("boom")):
            summary = reconcile_subscriptions()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "active")  # untouched
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["checked"], 0)

    @mock.patch(_SYNC)
    def test_terminal_subs_not_retrieved(self, _sync):
        # A canceled local sub is outside the reconcile set. (make_user fires
        # the signup signal which get-or-creates a FREE sub now that a FREE
        # plan exists, so update rather than create.)
        other = make_user("gone")
        Subscription.objects.update_or_create(
            user=other,
            defaults={"plan": self.free, "status": "canceled", "stripe_subscription_id": "sub_gone"},
        )
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.Subscription.retrieve", return_value=self._stripe_sub("active")) as retrieve:
            reconcile_subscriptions()
        # Only the one active sub was re-pulled.
        self.assertEqual(retrieve.call_count, 1)
        self.assertEqual(retrieve.call_args.args, ("sub_1",))
