"""Unit tests for the v1 IsPaid permission.

Mirrors the @require_paid entitlement gate: entitled subscription allows,
non-entitled denies, ANALYTICS_FREE_FOR_ALL grants everyone.
"""

from __future__ import annotations

from django.test import override_settings

from core.api.permissions import IsPaid
from core.api.tests.base import V1APITestCase
from core.billing.models import Plan, Subscription


# STRIPE_SECRET_KEY="" so the Plan post_save signal skips the real Stripe
# catalog push — keeps these unit tests hermetic and fast.
@override_settings(ANALYTICS_FREE_FOR_ALL=False, STRIPE_SECRET_KEY="")
class IsPaidPermissionTests(V1APITestCase):
    def setUp(self):
        self.perm = IsPaid()
        self.user = self.make_user("payer")

    def _subscribe(self, *, analytics: bool, status: str = "active"):
        plan = Plan.objects.create(
            code=f"p_{analytics}_{status}",
            name="Plan",
            amount_cents=0,
            features={"analytics": analytics},
        )
        Subscription.objects.update_or_create(
            user=self.user, defaults={"plan": plan, "status": status},
        )

    def _check(self):
        return self.perm.has_permission(_FakeRequest(self.user), view=None)

    def test_entitled_user_allowed(self):
        self._subscribe(analytics=True, status="active")
        self.assertTrue(self._check())

    def test_non_entitled_plan_denied(self):
        self._subscribe(analytics=False, status="active")
        self.assertFalse(self._check())

    def test_canceled_subscription_denied(self):
        self._subscribe(analytics=True, status="canceled")
        self.assertFalse(self._check())

    def test_no_subscription_denied(self):
        self.assertFalse(self._check())

    @override_settings(ANALYTICS_FREE_FOR_ALL=True)
    def test_free_for_all_allows_everyone(self):
        # No subscription, kill-switch on -> allowed.
        self.assertTrue(self._check())


class _FakeRequest:
    def __init__(self, user):
        self.user = user
