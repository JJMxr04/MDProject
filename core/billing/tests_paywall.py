"""Fake-paywall interstitial (roadmap Phase 3 §4).

The wall exists only while BOTH flags are on; it intercepts users who
are riding the ANALYTICS_FREE_FOR_ALL grant (no real PRO entitlement),
once per session, and records impressions + upgrade clicks as
ProductEvents.
"""

from __future__ import annotations

from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.billing.decorators import require_paid
from core.billing.models import Plan, Subscription
from core.billing.views.paywall import PAYWALL_ACK_SESSION_KEY
from core.match.tests.factories import make_user
from core.metrics.models import ProductEvent


@require_paid
def _gated_view(request):
    return HttpResponse("ok")


def _request_for(user, path="/web/portal/analytics/league/NBA/"):
    request = RequestFactory().get(path)
    request.user = user
    request.session = SessionStore()
    return request


def _make_free_user(suffix):
    user = make_user(suffix)
    # Truthy mirror marker so @require_paid skips the aggregator call.
    user.aggrigator_external_id = user.public_id
    return user


# STRIPE_SECRET_KEY blanked so Plan.post_save skips the real catalog
# sync (signals.py guards on it) — keeps these tests offline.
@override_settings(
    FAKE_PAYWALL_ENABLED=True, ANALYTICS_FREE_FOR_ALL=True, STRIPE_SECRET_KEY="",
)
class RequirePaidInterstitialTests(TestCase):
    def test_free_user_redirected_to_paywall_once(self):
        user = _make_free_user("wall")
        request = _request_for(user)
        response = _gated_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core-portal:billing-paywall"), response.url)
        self.assertIn("next=", response.url)

    def test_acked_session_passes_through(self):
        user = _make_free_user("acked")
        request = _request_for(user)
        request.session[PAYWALL_ACK_SESSION_KEY] = True
        response = _gated_view(request)
        self.assertEqual(response.status_code, 200)

    def test_real_pro_subscriber_never_walled(self):
        user = _make_free_user("pro")
        plan = Plan.objects.create(
            code="PRO", name="Pro", amount_cents=900,
            features={"analytics": True},
        )
        Subscription.objects.create(user=user, plan=plan, status="active")
        response = _gated_view(_request_for(user))
        self.assertEqual(response.status_code, 200)

    @override_settings(FAKE_PAYWALL_ENABLED=False)
    def test_flag_off_means_no_wall(self):
        user = _make_free_user("off")
        response = _gated_view(_request_for(user))
        self.assertEqual(response.status_code, 200)


@override_settings(
    FAKE_PAYWALL_ENABLED=True, ANALYTICS_FREE_FOR_ALL=True, STRIPE_SECRET_KEY="",
)
class PaywallViewTests(TestCase):
    def setUp(self):
        self.user = make_user("pwv")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:billing-paywall")

    def test_get_renders_and_tracks_impression(self):
        response = self.client.get(self.url, {"next": "/web/portal/dashboard/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upgrade to PRO")
        self.assertTrue(
            ProductEvent.objects.filter(user=self.user, name="paywall_viewed").exists()
        )

    def test_continue_acks_session_and_redirects(self):
        response = self.client.post(
            reverse("core-portal:billing-paywall-continue"),
            {"next": "/web/portal/dashboard/"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/web/portal/dashboard/")
        self.assertTrue(self.client.session.get(PAYWALL_ACK_SESSION_KEY))

    def test_unsafe_next_falls_back_to_dashboard(self):
        response = self.client.post(
            reverse("core-portal:billing-paywall-continue"),
            {"next": "https://evil.example/phish"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core-portal:portal-dashboard"))

    @override_settings(STRIPE_SECRET_KEY="")
    def test_upgrade_click_tracked_even_when_checkout_unconfigured(self):
        response = self.client.post(
            reverse("core-portal:billing-checkout"),
            {"source": "paywall", "next": "/web/portal/dashboard/"},
        )
        # Stripe isn't configured in tests → bounced to upgrade page,
        # but the willingness-to-pay click is already recorded and the
        # session is acked (no wall loop on return).
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ProductEvent.objects.filter(
                user=self.user, name="paywall_upgrade_clicked",
            ).exists()
        )
        self.assertTrue(self.client.session.get(PAYWALL_ACK_SESSION_KEY))

    @override_settings(FAKE_PAYWALL_ENABLED=False, ANALYTICS_FREE_FOR_ALL=False)
    def test_flags_off_bounces_to_billing_index(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("core-portal:billing-index"))
