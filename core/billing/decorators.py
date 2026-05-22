"""``@require_paid`` — portal-side gate for analytics views.

Three things this does, in order:

1. ``@login_required`` chain — anonymous users go to the login page.
2. Entitlement gate — FREE / canceled / unpaid users go to
   /billing/upgrade/. The check goes through
   ``core.billing.entitlement.user_can_access_analytics`` so the
   platform-wide kill-switch (``ANALYTICS_FREE_FOR_ALL``) and missing-
   Subscription edge cases route the same as the normal path.
3. Defensive aggrigator provisioning — if a *paid* PRO user has no
   ``aggrigator_api_key`` (DB restore, signup signal crashed, etc.),
   provision them inline so the downstream analytics call has a key.
   This step is SKIPPED for kill-switch FREE users — their FREE-tier
   key from the signup signal is what analytics endpoints see, and
   upgrading them to PRO at the aggrigator side would misrepresent
   what they're actually paying for.

The decorator is intentionally permissive about the third step: a
transient aggrigator failure renders the page in an empty-state instead
of 500ing. The user retries by refreshing.

See subscription-plan/05-access-control.md §1.
"""

from __future__ import annotations

import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from core.billing.entitlement import user_can_access_analytics
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

        # Inline aggrigator-key backfill — only runs for paid PRO users.
        # Kill-switch FREE users skip this: they were provisioned at
        # FREE tier by the signup signal, that's what their key is, and
        # bumping them to PRO at the aggrigator just to satisfy an
        # "everyone is free for now" toggle would lie about tier.
        free_for_all = getattr(settings, "ANALYTICS_FREE_FOR_ALL", False)
        if not free_for_all and not user.aggrigator_api_key:
            logger.warning(
                "PRO user %s missing aggrigator_api_key — provisioning inline",
                user.pk,
            )
            try:
                key = aggrigator_internal.provision_user(user, tier="PRO")
                if key:
                    User.objects.filter(pk=user.pk).update(
                        aggrigator_api_key=key,
                        aggrigator_external_id=user.public_id,
                    )
                    user.aggrigator_api_key = key
                    user.aggrigator_external_id = user.public_id
            except Exception:
                logger.exception(
                    "inline aggrigator provisioning failed for %s", user.pk,
                )
                messages.warning(
                    request,
                    "Analytics is unavailable for a moment — try again shortly.",
                )
                return redirect("core-portal:billing-upgrade")

        return view_func(request, *args, **kwargs)
    return wrapper
