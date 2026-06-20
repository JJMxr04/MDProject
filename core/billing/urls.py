"""Billing portal URLs — mounted at ``/web/portal/billing/`` from
``core/portal/urls.py`` so they all live in the ``core-portal:`` namespace.

The Stripe webhook is registered separately in ``CoreRoot/urls.py`` at
the top-level path ``/billing/stripe/webhook`` (matching the pattern used
by the existing ``/sportgameodds/webhook``) — Stripe needs a stable,
short, namespace-free URL.
"""

from __future__ import annotations

from django.urls import path

from core.billing import views

urlpatterns = [
    path("", views.billing_index, name="billing-index"),
    path("upgrade/", views.upgrade_page, name="billing-upgrade"),
    path("checkout/", views.start_checkout, name="billing-checkout"),
    path("thanks/", views.checkout_thanks, name="billing-thanks"),
    path("portal/", views.open_customer_portal, name="billing-portal"),
    path("refresh/", views.refresh_subscription, name="billing-refresh"),
]
