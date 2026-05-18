"""Stripe SDK initialization.

Pinned API version so a Stripe-side surface change can't silently break
us. The secret key is read from settings; we never read it directly from
``os.environ`` so a test override via Django ``override_settings`` works.

A startup warning fires if the secret key is unset — useful in dev, hard
fail in prod (enforced in ``CoreRoot/settings.py``).
"""

from __future__ import annotations

import logging

import stripe
from django.conf import settings

logger = logging.getLogger(__name__)

# Pinned for predictability — bump deliberately, after reading the Stripe
# changelog. Default matches what stripe-python 12.x ships with so the SDK
# and our explicit pin agree out of the box. The mismatch warning Stripe
# prints on the FIRST API call tells us when it's time to consider an
# upgrade.
DEFAULT_API_VERSION = "2025-07-30.basil"


def configure() -> None:
    """Apply the secret + API version to the global Stripe client.

    Idempotent — safe to call repeatedly. Called once at app startup
    (from ``BillingConfig.ready()`` once we wire it) and again from
    tests that swap in fakes via ``settings.override``.
    """
    stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "") or ""
    stripe.api_version = getattr(
        settings, "STRIPE_API_VERSION", DEFAULT_API_VERSION,
    )
    if not stripe.api_key:
        # Don't crash — code paths that actually call Stripe will raise
        # their own clear errors. Just make the misconfig discoverable.
        logger.warning(
            "STRIPE_SECRET_KEY is unset — Stripe API calls will fail. "
            "Set it in .env (sk_test_... for dev, sk_live_... for prod)."
        )
    elif stripe.api_key.startswith("pk_"):
        # Catch the most common misconfig — putting the publishable key
        # (pk_*) in STRIPE_SECRET_KEY. Stripe's 403 error mentions this
        # but only at first API-call time; we want it visible at boot.
        logger.error(
            "STRIPE_SECRET_KEY appears to be a PUBLISHABLE key (pk_*). "
            "Catalog writes will 403. Use the SECRET key (sk_test_... or "
            "sk_live_...) — find it in Stripe Dashboard → API keys. "
            "Move the pk_* value to STRIPE_PUBLISHABLE_KEY (or leave it "
            "blank; the subscription redirect flow doesn't need it)."
        )


# Eager configuration so import-time use ("stripe.Customer.create" in a
# view module load) works without the caller needing to call configure().
configure()
