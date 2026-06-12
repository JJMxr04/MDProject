"""``@require_paid`` — portal-side gate for analytics views.

Three things this does, in order:

1. ``@login_required`` chain — anonymous users go to the login page.
2. Entitlement gate — FREE / canceled / unpaid users go to
   /billing/upgrade/. The check goes through
   ``core.billing.entitlement.user_can_access_analytics`` so the
   platform-wide kill-switch (``ANALYTICS_FREE_FOR_ALL``) and missing-
   Subscription edge cases route the same as the normal path.
3. Defensive tenant-user mirror — if the user was never mirrored into
   the aggregator (signup signal crashed, DB restore, account predates
   billing), provision the tenant *user* row now so per-user data calls
   (bets, X-Acting-User) can attribute to them. Since the service-key
   cutover (plan §6.4, roadmap Phase 2) NO per-user API key is issued or
   stored — auth rides the single service key in aggrigator_client.

The decorator is intentionally permissive about the third step: a
transient aggrigator failure renders the page in an empty-state instead
of 500ing. The user retries by refreshing.

See subscription-plan/05-access-control.md §1.
"""

from __future__ import annotations

import logging
from functools import wraps

from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from core.billing.entitlement import (
    user_can_access_analytics,
    user_entitled_ignoring_killswitch,
)
from core.billing.services import aggrigator_internal
from core.user.models import User

logger = logging.getLogger(__name__)


def require_paid(view_func):
    """Wrap a portal view: redirect FREE/canceled to /billing/upgrade/."""
    @wraps(view_func)
    @login_required(login_url="/auth/login/")
    def wrapper(request, *args, **kwargs):
        user = request.user

        if not user_can_access_analytics(user):
            return redirect("core-portal:billing-upgrade")

        # Fake paywall (roadmap Phase 3 §4): while the free-for-all
        # kill-switch is granting access, show non-entitled users the
        # interstitial once per session before letting them through.
        # Import here, not at module top — paywall.py imports billing
        # models and this module loads early.
        if (
            getattr(settings, "FAKE_PAYWALL_ENABLED", False)
            and getattr(settings, "ANALYTICS_FREE_FOR_ALL", False)
        ):
            from core.billing.views.paywall import PAYWALL_ACK_SESSION_KEY
            if (
                not request.session.get(PAYWALL_ACK_SESSION_KEY)
                and not user_entitled_ignoring_killswitch(user)
            ):
                return redirect(
                    reverse("core-portal:billing-paywall")
                    + "?" + urlencode({"next": request.get_full_path()})
                )

        # Defensive tenant-user mirror (no key — see module docstring).
        # ``aggrigator_external_id`` doubles as the "already mirrored"
        # marker; the internal provision endpoint is idempotent so a
        # repeat for an already-mirrored user is a cheap 200.
        if not user.aggrigator_external_id:
            try:
                aggrigator_internal.provision_user(user, tier="FREE")
                User.objects.filter(pk=user.pk).update(
                    aggrigator_external_id=user.public_id,
                )
                user.aggrigator_external_id = user.public_id
            except Exception:
                # Non-fatal: shared-data analytics works regardless (the
                # service key authenticates); only bets attribution
                # would 404 until the mirror succeeds on a later visit.
                logger.exception(
                    "inline aggrigator tenant-user mirror failed for %s", user.pk,
                )

        return view_func(request, *args, **kwargs)
    return wrapper
