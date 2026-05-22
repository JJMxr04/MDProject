"""Stripe configuration introspection + one-click webhook setup.

Used by the admin "Stripe Setup" page (``/admin/stripe-setup/``) to:

- Report what mode the configured secret key is in (test vs live).
- Show the API version the SDK is pinned to + the API version Stripe
  uses by default for this account.
- List the webhook events MDProject subscribes to, plus the capabilities
  Stripe must allow on the secret key.
- Find or create a Stripe ``webhook_endpoint`` pointing at this
  installation's ``/billing/stripe/webhook``.

Kept deliberately read-mostly: the only mutating call is
``create_webhook_endpoint``, and the admin page refuses it when an
endpoint with the same URL already exists in the current account."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

import stripe
from django.conf import settings

# Side-effect import — wires our API key + pinned version onto the
# global stripe SDK at module load.
from core.billing import stripe_client  # noqa: F401

logger = logging.getLogger(__name__)


# ---- subscription configuration --------------------------------------------

# Events MDProject's webhook receiver actually handles or treats as
# expected no-ops (see ``core/billing/views/webhook.py:_HANDLERS``). If
# you wire a new handler over there, add the type here so the setup page
# subscribes to it on next webhook re-create.
WEBHOOK_EVENTS: list[str] = [
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.trial_will_end",
    "invoice.payment_succeeded",
    "invoice.payment_failed",
]


@dataclass(frozen=True)
class RequiredCapability:
    """One row in the "Permissions Stripe must grant the key" table.

    Used to spell out — for an operator creating a *restricted* key in
    the Stripe Dashboard — what scopes the integration needs. A standard
    secret key (``sk_test_...`` / ``sk_live_...``) has all of these by
    default; only restricted keys need the operator to tick boxes."""
    resource: str
    access: str        # "read" / "write"
    used_for: str


REQUIRED_CAPABILITIES: list[RequiredCapability] = [
    RequiredCapability(
        resource="Customers",
        access="write",
        used_for=(
            "Create / delete Stripe Customers from the admin user form "
            "and the ``reset_stripe_customers`` management command."
        ),
    ),
    RequiredCapability(
        resource="Checkout Sessions",
        access="write",
        used_for="Mint hosted Checkout sessions when a user clicks Subscribe.",
    ),
    RequiredCapability(
        resource="Subscriptions",
        access="read",
        used_for="Resolve subscription state when a user revisits the portal.",
    ),
    RequiredCapability(
        resource="Billing Portal",
        access="write",
        used_for="Open the Stripe-hosted portal for self-service billing changes.",
    ),
    RequiredCapability(
        resource="Webhook Endpoints",
        access="write",
        used_for=(
            "List / create the webhook endpoint from this Setup page. "
            "Not needed once the webhook is in place — you can revoke "
            "after initial setup."
        ),
    ),
    RequiredCapability(
        resource="Products + Prices",
        access="write",
        used_for=(
            "Optional — only required if you use the catalog sync to "
            "publish Plan rows to Stripe."
        ),
    ),
]


# ---- snapshot view ---------------------------------------------------------


@dataclass(frozen=True)
class StripeStatus:
    """Everything the Setup page needs to render the "where am I right
    now" block at the top. ``error`` is set if the key can't even
    authenticate (so we render a friendly hint instead of a stack
    trace)."""
    key_present: bool
    key_mode: str          # "test", "live", "publishable", "unset"
    pinned_api_version: str
    account_id: str | None
    account_email: str | None
    account_default_api_version: str | None
    charges_enabled: bool | None
    payouts_enabled: bool | None
    error: str | None = None


def status() -> StripeStatus:
    """Fetch the current Stripe-side state. Wraps every external call so
    a misconfigured key surfaces as a banner, not a 500."""
    raw_key = getattr(settings, "STRIPE_SECRET_KEY", "") or ""
    pinned = getattr(
        settings, "STRIPE_API_VERSION", stripe_client.DEFAULT_API_VERSION,
    )

    if not raw_key:
        return StripeStatus(
            key_present=False, key_mode="unset",
            pinned_api_version=pinned,
            account_id=None, account_email=None,
            account_default_api_version=None,
            charges_enabled=None, payouts_enabled=None,
            error="STRIPE_SECRET_KEY is not set in the environment.",
        )

    mode = (
        "publishable" if raw_key.startswith("pk_") else
        "test" if raw_key.startswith("sk_test_") else
        "live" if raw_key.startswith("sk_live_") else
        "unknown"
    )

    if mode == "publishable":
        return StripeStatus(
            key_present=True, key_mode=mode,
            pinned_api_version=pinned,
            account_id=None, account_email=None,
            account_default_api_version=None,
            charges_enabled=None, payouts_enabled=None,
            error=(
                "STRIPE_SECRET_KEY appears to hold a publishable key "
                "(``pk_*``). Replace it with the SECRET key (``sk_test_...``)."
            ),
        )

    try:
        acct = stripe.Account.retrieve()
    except stripe.error.StripeError as exc:
        return StripeStatus(
            key_present=True, key_mode=mode,
            pinned_api_version=pinned,
            account_id=None, account_email=None,
            account_default_api_version=None,
            charges_enabled=None, payouts_enabled=None,
            error=f"Account fetch failed: {exc.user_message or exc}",
        )

    return StripeStatus(
        key_present=True,
        key_mode=mode,
        pinned_api_version=pinned,
        account_id=acct.get("id"),
        account_email=acct.get("email"),
        # ``api_version`` on Account is the version Stripe will use for
        # webhook deliveries when the endpoint doesn't override it. We
        # show both so the operator can see when our SDK pin drifts.
        account_default_api_version=acct.get("api_version"),
        charges_enabled=acct.get("charges_enabled"),
        payouts_enabled=acct.get("payouts_enabled"),
    )


# ---- webhook endpoint helpers ----------------------------------------------


@dataclass(frozen=True)
class EndpointSummary:
    """Light wrapper around a Stripe ``webhook_endpoint`` resource."""
    id: str
    url: str
    status: str
    api_version: str | None
    enabled_events: list[str]


def list_endpoints() -> list[EndpointSummary]:
    """Every webhook_endpoint configured on the current Stripe account."""
    out: list[EndpointSummary] = []
    listing = stripe.WebhookEndpoint.list(limit=100)
    for ep in listing.auto_paging_iter():
        out.append(EndpointSummary(
            id=ep["id"],
            url=ep.get("url", ""),
            status=ep.get("status", ""),
            api_version=ep.get("api_version"),
            enabled_events=list(ep.get("enabled_events") or []),
        ))
    return out


def find_endpoint_by_url(url: str) -> Optional[EndpointSummary]:
    """Return the FIRST endpoint whose URL matches ``url`` exactly.

    Stripe stores the URL as the operator entered it (no normalization),
    so a trailing-slash mismatch counts as a different endpoint. The
    setup form uses ``request.build_absolute_uri(reverse(...))`` to
    compute its candidate URL, so comparisons there are stable."""
    normalized = url.strip()
    for ep in list_endpoints():
        if ep.url == normalized:
            return ep
    return None


@dataclass(frozen=True)
class CreatedEndpoint:
    """Result of ``create_webhook_endpoint``. ``secret`` is the
    plaintext ``whsec_...`` Stripe returns exactly once — the operator
    must copy it into ``STRIPE_WEBHOOK_SECRET`` before reload."""
    id: str
    url: str
    secret: str
    api_version: str | None
    enabled_events: list[str]
    dashboard_url: str


def create_webhook_endpoint(
    url: str, *,
    events: Iterable[str] = WEBHOOK_EVENTS,
    description: str = "MDProject (auto-created via Stripe Setup)",
) -> CreatedEndpoint:
    """Create a fresh webhook endpoint on the current Stripe account.

    Refuses (raises ``ValueError``) if an endpoint with the same URL
    already exists — callers should call ``find_endpoint_by_url`` first
    and surface that to the operator so they can delete it manually in
    the Stripe Dashboard. We don't auto-delete: a webhook secret in
    use elsewhere would silently die.

    The ``api_version`` argument is intentionally omitted — letting it
    default to the account's pinned version means webhook deliveries
    use the same payload shape the SDK does, no drift to debug.
    """
    if find_endpoint_by_url(url) is not None:
        raise ValueError(
            f"A webhook endpoint with URL {url!r} already exists. Delete "
            "it in the Stripe Dashboard first (or update the local "
            "STRIPE_WEBHOOK_SECRET to match it)."
        )

    ep = stripe.WebhookEndpoint.create(
        url=url,
        enabled_events=list(events),
        description=description,
    )
    secret = ep.get("secret") or ""
    if not secret:
        # Shouldn't happen — Stripe always returns ``secret`` on the
        # create response — but defensively flag it because everything
        # downstream needs it.
        raise RuntimeError(
            "Stripe returned no ``secret`` on the webhook_endpoint "
            "create response. Inspect the endpoint manually."
        )

    raw_key = getattr(settings, "STRIPE_SECRET_KEY", "") or ""
    test_segment = "test/" if raw_key.startswith("sk_test_") else ""
    dashboard_url = (
        f"https://dashboard.stripe.com/{test_segment}"
        f"webhooks/{ep['id']}"
    )

    return CreatedEndpoint(
        id=ep["id"],
        url=ep.get("url", url),
        secret=secret,
        api_version=ep.get("api_version"),
        enabled_events=list(ep.get("enabled_events") or []),
        dashboard_url=dashboard_url,
    )
