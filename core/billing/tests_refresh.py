"""Self-serve subscription refresh — the user-facing recovery for a payer
stranded on FREE by webhook resolve drift, plus the ``subscription_pending``
signal that decides when to offer it instead of a pay-again CTA.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from core.billing.entitlement import subscription_pending
from core.billing.models import Plan, Subscription
from core.billing.services.subscription_sync import SubscriptionSyncError, SyncReport
from core.match.tests.factories import make_user


def _free_row(user, status="active"):
    free = Plan.objects.filter(code="FREE").first() or Plan.objects.create(
        code="FREE", name="Free", amount_cents=0,
        features={"analytics": False}, is_active=True,
    )
    return Subscription.objects.create(user=user, plan=free, status=status)


def _with_customer(user):
    user.stripe_customer_id = "cus_1"
    user.save(update_fields=["stripe_customer_id"])
    return user


class SubscriptionPendingTests(TestCase):
    def setUp(self):
        self.user = make_user("u")

    def test_free_user_without_customer_is_not_pending(self):
        _free_row(self.user)
        self.assertFalse(subscription_pending(self.user))

    def test_customer_plus_free_active_is_pending(self):
        _with_customer(self.user)
        _free_row(self.user)
        self.assertTrue(subscription_pending(self.user))

    def test_canceled_ex_pro_is_not_pending(self):
        _with_customer(self.user)
        _free_row(self.user, status="canceled")
        self.assertFalse(subscription_pending(self.user))

    def test_entitled_pro_is_not_pending(self):
        _with_customer(self.user)
        pro = Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900,
            features={"analytics": True}, is_active=True,
        )
        Subscription.objects.create(user=self.user, plan=pro, status="active")
        self.assertFalse(subscription_pending(self.user))

    def test_customer_but_no_row_is_pending(self):
        _with_customer(self.user)  # has a customer, sub row not provisioned yet
        self.assertTrue(subscription_pending(self.user))


_REFRESH = "core.billing.views.refresh.refresh_from_stripe"


class RefreshViewTests(TestCase):
    def setUp(self):
        self.user = make_user("payer")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:billing-refresh")
        self.upgrade = reverse("core-portal:billing-upgrade")

    def _report(self, **kw):
        base = dict(
            found_on_stripe=True, stripe_subscription_id="sub_1",
            status="active", plan_code="PRO", aggrigator_synced=True,
        )
        base.update(kw)
        return SyncReport(**base)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_pro_found_redirects_with_success(self):
        with mock.patch(_REFRESH, return_value=self._report()):
            r = self.client.post(self.url, {"next": self.upgrade}, follow=True)
        self.assertContains(r, "now active")

    def test_no_active_sub_redirects_with_info(self):
        with mock.patch(_REFRESH, return_value=self._report(found_on_stripe=False, plan_code="FREE")):
            r = self.client.post(self.url, {"next": self.upgrade}, follow=True)
        self.assertContains(r, "couldn&#x27;t find an active subscription")

    def test_sync_error_redirects_with_warning(self):
        err = SubscriptionSyncError("boom", user_message="No Stripe Customer linked.")
        with mock.patch(_REFRESH, side_effect=err):
            r = self.client.post(self.url, {"next": self.upgrade}, follow=True)
        self.assertContains(r, "No Stripe Customer linked.")

    def test_open_redirect_next_is_rejected(self):
        with mock.patch(_REFRESH, return_value=self._report()):
            r = self.client.post(self.url, {"next": "http://evil.example/"})
        self.assertRedirects(r, self.upgrade, fetch_redirect_response=False)
