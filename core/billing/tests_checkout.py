"""Checkout + Customer Portal flow (Phase 10 verify).

End-to-end coverage of the redirect-to-Stripe flow with Stripe mocked: the
upgrade page's Subscribe button, ``start_checkout`` session creation + its
guard rails, the Customer Portal hand-off, and the billing index CTAs.

Plans are created with ``STRIPE_SECRET_KEY=""`` so the Plan post_save signal
skips the real catalog push; the key is overridden only around the request
under test.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from core.billing.models import Plan, Subscription
from core.match.tests.factories import make_user
from core.metrics.models import ProductEvent

_KEY = "sk_test_dummy"


@override_settings(STRIPE_SECRET_KEY="")
class StartCheckoutTests(TestCase):
    def setUp(self):
        self.user = make_user("buyer")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:billing-checkout")

    def _pro(self, *, stripe_price_id="price_123", trial_days=0):
        return Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900,
            features={"analytics": True}, trial_days=trial_days,
            stripe_price_id=stripe_price_id, is_active=True,
        )

    def test_creates_session_and_redirects(self):
        self._pro()
        fake = mock.Mock(url="https://stripe.test/checkout/xyz")
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.checkout.Session.create", return_value=fake) as create:
            resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://stripe.test/checkout/xyz")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "subscription")
        self.assertEqual(kwargs["line_items"], [{"price": "price_123", "quantity": 1}])
        self.assertEqual(kwargs["client_reference_id"], str(self.user.public_id))
        self.assertTrue(ProductEvent.objects.filter(name="checkout_started").exists())

    def test_reuses_existing_stripe_customer(self):
        self._pro()
        self.user.stripe_customer_id = "cus_existing"
        self.user.save(update_fields=["stripe_customer_id"])
        fake = mock.Mock(url="https://stripe.test/checkout/xyz")
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.checkout.Session.create", return_value=fake) as create:
            self.client.post(self.url)
        self.assertEqual(create.call_args.kwargs.get("customer"), "cus_existing")

    def test_first_time_includes_trial_email_prefill(self):
        self._pro(trial_days=7)
        fake = mock.Mock(url="https://stripe.test/checkout/xyz")
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.checkout.Session.create", return_value=fake) as create:
            self.client.post(self.url)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["subscription_data"].get("trial_period_days"), 7)
        self.assertEqual(kwargs.get("customer_email"), self.user.email)

    def test_no_stripe_key_redirects_to_upgrade(self):
        self._pro()
        resp = self.client.post(self.url)  # key is "" from class override
        self.assertRedirects(resp, reverse("core-portal:billing-upgrade"), fetch_redirect_response=False)

    def test_missing_pro_plan_redirects_to_upgrade(self):
        with override_settings(STRIPE_SECRET_KEY=_KEY):
            resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse("core-portal:billing-upgrade"), fetch_redirect_response=False)

    def test_stripe_error_redirects_to_upgrade(self):
        self._pro()
        import stripe
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.checkout.Session.create", side_effect=stripe.error.StripeError("boom")):
            resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse("core-portal:billing-upgrade"), fetch_redirect_response=False)


@override_settings(STRIPE_SECRET_KEY="")
class CustomerPortalTests(TestCase):
    def setUp(self):
        self.user = make_user("subscriber")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:billing-portal")

    def test_redirects_to_portal_session(self):
        self.user.stripe_customer_id = "cus_x"
        self.user.save(update_fields=["stripe_customer_id"])
        fake = mock.Mock(url="https://stripe.test/portal/abc")
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.billing_portal.Session.create", return_value=fake) as create:
            resp = self.client.post(self.url, {"flow": "manage"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], "https://stripe.test/portal/abc")
        self.assertEqual(create.call_args.kwargs["customer"], "cus_x")

    def test_no_customer_redirects_to_upgrade(self):
        with override_settings(STRIPE_SECRET_KEY=_KEY):
            resp = self.client.post(self.url)
        self.assertRedirects(resp, reverse("core-portal:billing-upgrade"), fetch_redirect_response=False)

    def test_cancel_without_subscription_falls_back_to_manage(self):
        self.user.stripe_customer_id = "cus_x"
        self.user.save(update_fields=["stripe_customer_id"])
        fake = mock.Mock(url="https://stripe.test/portal/abc")
        with override_settings(STRIPE_SECRET_KEY=_KEY), \
                mock.patch("stripe.billing_portal.Session.create", return_value=fake) as create:
            resp = self.client.post(self.url, {"flow": "cancel"})
        self.assertEqual(resp.status_code, 302)
        # No subscription on file → no flow_data (manage home), not a 500.
        self.assertNotIn("flow_data", create.call_args.kwargs)

    def test_no_stripe_key_redirects_to_index(self):
        resp = self.client.post(self.url)  # key "" from class override
        self.assertRedirects(resp, reverse("core-portal:billing-index"), fetch_redirect_response=False)


@override_settings(STRIPE_SECRET_KEY="")
class BillingPagesTests(TestCase):
    def setUp(self):
        self.user = make_user("viewer")
        self.client.force_login(self.user)

    def test_upgrade_page_renders_subscribe_form(self):
        Plan.objects.create(code="PRO", name="Pro", amount_cents=900, features={"analytics": True}, stripe_price_id="price_1")
        resp = self.client.get(reverse("core-portal:billing-upgrade"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("core-portal:billing-checkout"))

    def test_thanks_page_renders(self):
        resp = self.client.get(reverse("core-portal:billing-thanks") + "?session_id=cs_test_1")
        self.assertEqual(resp.status_code, 200)

    def test_index_free_shows_upgrade_cta(self):
        resp = self.client.get(reverse("core-portal:billing-index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("core-portal:billing-upgrade"))

    def test_index_pro_shows_manage(self):
        pro = Plan.objects.create(code="PRO", name="Pro", amount_cents=900, features={"analytics": True}, stripe_price_id="price_1")
        Subscription.objects.update_or_create(
            user=self.user,
            defaults={"plan": pro, "status": "active", "stripe_subscription_id": "sub_1"},
        )
        self.user.stripe_customer_id = "cus_1"
        self.user.save(update_fields=["stripe_customer_id"])
        resp = self.client.get(reverse("core-portal:billing-index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse("core-portal:billing-portal"))
