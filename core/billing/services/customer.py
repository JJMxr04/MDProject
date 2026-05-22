"""Stripe Customer lifecycle helpers.

Three operations, used by the admin Reconnect / Create buttons and the
``reset_stripe_customers`` management command:

- ``create_customer(user)`` — call ``stripe.Customer.create``, save the
  new ``cus_...`` on the user, return it. Overwrites any existing id;
  callers that want delete-then-create should use ``reset_customer``.
- ``reconnect_customer(user)`` — search Stripe by ``user.email``. If a
  matching Customer exists (most recent if there are multiples), save its
  id on the user and return it. Returns ``None`` when no match — the
  caller decides whether to fall back to create.
- ``reset_customer(user)`` — best-effort delete the previously stored
  ``cus_...`` then create a fresh one. Use when swapping Stripe test
  accounts so we don't leak orphan customers in the *current* account.

All three are wrapped in ``StripeCustomerError`` so callers can ``except``
once. The underlying ``stripe.error.StripeError.user_message`` is carried
through for surfacing in admin messages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import stripe

# Import for side effects — configures the Stripe SDK with our API key
# + pinned version at module load time.
from core.billing import stripe_client  # noqa: F401
from core.user.models import User

logger = logging.getLogger(__name__)


class StripeCustomerError(Exception):
    """Stripe API call failed. ``user_message`` is safe to show operators."""

    def __init__(self, message: str, *, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


@dataclass
class ResetReport:
    """Per-user outcome of ``reset_customer`` — surfaced by the manage
    command's per-row summary."""
    user_id: int
    email: str
    old_customer_id: str
    new_customer_id: str
    deleted_old: bool
    delete_skipped_reason: str | None
    error: str | None = None


# ---- single-user operations ------------------------------------------------


def create_customer(user: User) -> str:
    """Create a fresh Stripe Customer and save the id on ``user``.

    Overwrites ``user.stripe_customer_id`` if it was already set. Callers
    that want to delete the previous Stripe-side customer first should
    call ``reset_customer`` instead.
    """
    try:
        cust = stripe.Customer.create(
            email=user.email,
            name=user.name or user.username,
            metadata=_metadata(user),
        )
    except stripe.error.StripeError as exc:
        logger.exception("stripe.Customer.create failed for user_id=%s", user.pk)
        raise StripeCustomerError(
            f"Stripe Customer create failed: {exc}",
            user_message=getattr(exc, "user_message", None) or str(exc),
        ) from exc

    cust_id = cust["id"]
    User.objects.filter(pk=user.pk).update(stripe_customer_id=cust_id)
    user.stripe_customer_id = cust_id
    logger.info(
        "Stripe customer created: user_id=%s email=%s cus=%s",
        user.pk, user.email, cust_id,
    )
    return cust_id


def reconnect_customer(user: User) -> Optional[str]:
    """Search Stripe for a Customer with ``user.email``. Save + return
    the most recently created match's id, or ``None`` when no Customer
    in the current Stripe account has this email.

    Useful after restoring from a backup, or when the local id was
    cleared but the Stripe-side Customer still exists."""
    try:
        # ``email=...`` is an exact match (case-insensitive on Stripe's
        # side). ``limit=10`` is plenty — a duplicate-email situation
        # means manual cleanup anyway, but we'd rather see it than
        # silently pick one of 100.
        listing = stripe.Customer.list(email=user.email, limit=10)
    except stripe.error.StripeError as exc:
        logger.exception("stripe.Customer.list failed for user_id=%s", user.pk)
        raise StripeCustomerError(
            f"Stripe Customer list failed: {exc}",
            user_message=getattr(exc, "user_message", None) or str(exc),
        ) from exc

    customers = list(listing.auto_paging_iter()) if hasattr(
        listing, "auto_paging_iter",
    ) else list(listing.get("data", []))
    if not customers:
        return None

    # Most-recently-created wins. Stripe returns objects newest-first by
    # default but we sort explicitly so a future API change can't bite us.
    customers.sort(key=lambda c: c.get("created") or 0, reverse=True)
    cust_id = customers[0]["id"]
    User.objects.filter(pk=user.pk).update(stripe_customer_id=cust_id)
    user.stripe_customer_id = cust_id
    logger.info(
        "Stripe customer reconnected: user_id=%s email=%s cus=%s "
        "(out of %d candidate(s))",
        user.pk, user.email, cust_id, len(customers),
    )
    return cust_id


def reset_customer(user: User) -> ResetReport:
    """Delete the old Stripe Customer (best-effort) then create a fresh one.

    Use when rotating Stripe test credentials and you want both sides to
    line up: every user gets a brand-new ``cus_...`` in the *current*
    Stripe account.

    Delete failures (404, permission issues, network) are logged and
    skipped — the create still runs. The report records ``deleted_old``
    so the operator can see what happened.
    """
    old_id = user.stripe_customer_id or ""
    deleted = False
    delete_skipped: str | None = None

    if not old_id:
        delete_skipped = "no previous id"
    else:
        try:
            stripe.Customer.delete(old_id)
            deleted = True
        except stripe.error.InvalidRequestError as exc:
            # Most common case: the old id points at a Customer in a
            # different (test) account, or one already deleted. Not
            # fatal — we still want the fresh create.
            delete_skipped = f"InvalidRequest: {exc}"
            logger.info(
                "reset_customer: skipped delete for user_id=%s old=%s — %s",
                user.pk, old_id, exc,
            )
        except stripe.error.StripeError as exc:
            delete_skipped = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "reset_customer: delete failed for user_id=%s old=%s — %s",
                user.pk, old_id, exc,
            )

    # If create blows up we still return a report (with ``error`` set)
    # rather than raising, so the manage command can keep walking.
    try:
        new_id = create_customer(user)
    except StripeCustomerError as exc:
        return ResetReport(
            user_id=user.pk,
            email=user.email,
            old_customer_id=old_id,
            new_customer_id="",
            deleted_old=deleted,
            delete_skipped_reason=delete_skipped,
            error=exc.user_message,
        )

    return ResetReport(
        user_id=user.pk,
        email=user.email,
        old_customer_id=old_id,
        new_customer_id=new_id,
        deleted_old=deleted,
        delete_skipped_reason=delete_skipped,
    )


# ---- helpers ---------------------------------------------------------------


def _metadata(user: User) -> dict[str, str]:
    """Stripe Customer.metadata payload — values must be strings.

    Keeping ``user_public_id`` here means a Stripe-side operator (or a
    webhook payload with the customer expanded) can resolve back to our
    user without a round-trip through the email."""
    return {
        "user_public_id": str(user.public_id),
        "user_pk": str(user.pk),
    }
