"""Single source of truth for "is this user PRO-entitled?".

Exists instead of a one-liner on ``Subscription`` because
``getattr(user, "subscription", None)`` doesn't catch Django's
``Subscription.DoesNotExist`` (only ``AttributeError``). Centralizing the
access protects every caller from that latent 500.

Phase 16 (D-16d) removed the platform-wide ``ANALYTICS_FREE_FOR_ALL`` kill
switch and made the analytics dashboard free; this check now reflects the
real Stripe entitlement only, and the PRO-gated surface is opponent scouting
(Phase 9). The name is kept for now; generalize to ``is_pro`` /
``plan.features`` when a second gated feature lands (subscription-plan
open-questions §6).

The ``Subscription.is_entitled_to_analytics`` property remains for templates
and code that already has a ``Subscription`` instance in hand.
"""

from __future__ import annotations


def user_can_access_analytics(user) -> bool:
    """True if ``user`` is PRO-entitled.

    - Anonymous users: False (callers should still gate with ``@login_required``).
    - Otherwise: defer to the Subscription's per-instance check, treating a
      missing Subscription row as "no access".
    """
    if not getattr(user, "is_authenticated", False):
        return False
    sub = _safe_subscription(user)
    if sub is None:
        return False
    return sub.is_entitled_to_analytics


def _safe_subscription(user):
    """Return ``user.subscription`` or None — catches the ``DoesNotExist``
    that the OneToOneField descriptor raises when no row exists.

    ``getattr(user, "subscription", None)`` is *not* sufficient here:
    Django raises ``Subscription.DoesNotExist`` (subclass of Exception,
    not AttributeError), so ``getattr`` doesn't swallow it.
    """
    # Import inside the function to avoid a circular import at module-load
    # time (``core.billing.models`` imports from ``django.conf``, which is
    # fine, but importing this module from ``core.billing.models`` would
    # cycle).
    from core.billing.models import Subscription
    try:
        return user.subscription
    except Subscription.DoesNotExist:
        return None
    except AttributeError:
        # Anonymous user or test double without the reverse relation.
        return None
