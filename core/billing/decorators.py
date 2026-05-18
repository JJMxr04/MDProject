"""``@require_paid`` — portal-side gate for analytics views.

Three things this does, in order:

1. ``@login_required`` chain — anonymous users go to the login page.
2. Subscription gate — FREE / canceled / unpaid users go to /billing/upgrade/.
3. Defensive aggrigator provisioning — if somehow this PRO user has no
   ``aggrigator_api_key`` (DB restore, signup signal crashed, etc.),
   provision them inline so the downstream analytics call has a key.

The decorator is intentionally permissive about the third step: a
transient aggrigator failure renders the page in an empty-state instead
of 500ing. The user retries by refreshing.

See subscription-plan/05-access-control.md §1.
"""

from __future__ import annotations

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from core.billing.services import aggrigator_internal
from core.user.models import User

logger = logging.getLogger(__name__)


def require_paid(view_func):
    """Wrap a portal view: redirect FREE/canceled to /billing/upgrade/."""
    @wraps(view_func)
    @login_required(login_url="/auth/login/")
    def wrapper(request, *args, **kwargs):
        user = request.user
        sub = getattr(user, "subscription", None)

        if sub is None or not sub.is_entitled_to_analytics:
            return redirect("core-portal:billing-upgrade")

        # Defensive backfill — should rarely trigger. The signup signal
        # provisions every new user; the one-shot backfill script covers
        # existing users at cutover. This catches edge cases (DB restore
        # without re-running backfill, signup signal raised, etc.).
        if not user.aggrigator_api_key:
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
