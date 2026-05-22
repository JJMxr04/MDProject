"""Single source of truth for "can this user use analytics?".

Two reasons this exists instead of a one-liner on ``Subscription``:

1. The kill-switch (``settings.ANALYTICS_FREE_FOR_ALL``) is platform-wide
   — it should grant access even to users whose ``Subscription`` row is
   missing (data restore, signup signal failure, etc.). The property on
   the Subscription instance can't be reached when the instance doesn't
   exist.

2. ``getattr(user, "subscription", None)`` doesn't catch Django's
   ``Subscription.DoesNotExist`` (only ``AttributeError``). Centralizing
   the access protects every caller from that latent 500.

The Subscription.is_entitled_to_analytics property remains for templates
and code that already has a ``Subscription`` instance in hand.
"""

from __future__ import annotations

from django.conf import settings


def user_can_access_analytics(user) -> bool:
    """True if ``user`` should see analytics surfaces.

    - Anonymous users: False (callers should still gate with ``@login_required``).
    - Kill-switch on: always True for any logged-in user.
    - Otherwise: defer to the Subscription's per-instance check, treating
      a missing Subscription row as "no access".
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(settings, "ANALYTICS_FREE_FOR_ALL", False):
        return True
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
