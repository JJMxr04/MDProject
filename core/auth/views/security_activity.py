"""Portal session-control actions on the Security page (tier 3)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_POST

from core.auth.services.login_security import (
    active_sessions_for_user,
    revoke_all_sessions,
    revoke_other_sessions,
    revoke_session,
)


def _back_to_sessions_tab():
    """Redirect back to the Security page with the Sessions tab pre-selected."""
    return redirect(f"{reverse('core-auth:2fa-security')}?tab=sessions")


@login_required
@require_POST
def logout_others(request):
    """Sign out every other session for this user; keep the current one."""
    n = revoke_other_sessions(request.user, keep_session_key=request.session.session_key)
    messages.success(request, f"Signed out of {n} other session{'' if n == 1 else 's'}.")
    return _back_to_sessions_tab()


@login_required
@require_POST
def revoke_one_session(request):
    """Sign out a single device/session the user picked from the list."""
    key = (request.POST.get("session_key") or "").strip()
    if revoke_session(request.user, key):
        messages.success(request, "That device has been signed out.")
    else:
        messages.error(request, "That session is no longer active.")
    return _back_to_sessions_tab()


@login_required
@require_POST
def revoke_session_confirm(request):
    """Interstitial: confirm signing out one device before it happens.
    POST (not GET) so the session key stays out of URLs, history, and logs."""
    key = (request.POST.get("session_key") or "").strip()
    target = next(
        (s for s in active_sessions_for_user(request.user, request.session.session_key)
         if s["session_key"] == key and not s["is_current"]),
        None,
    )
    if target is None:
        messages.error(request, "That session is no longer active.")
        return _back_to_sessions_tab()
    return render(request, "portal/security/confirm_revoke_session.html", {
        "active": "security",
        "session_key": key,
        "device_label": target["device_label"],
        "country": target["country"],
        "last_login_at": target["last_login_at"],
    })


@login_required
def not_me_confirm(request):
    """Interstitial: confirm the account-lockout action before executing it."""
    return render(request, "portal/security/confirm_not_me.html", {"active": "security"})


@login_required
@require_POST
def not_me(request):
    """'This wasn't me': revoke every session (including this one) and send the
    user into the password-reset flow to lock the intruder out."""
    revoke_all_sessions(request.user)
    auth_logout(request)  # flush the current session too
    return redirect("reset_password" if _url_exists("reset_password") else "core-auth:login")


def _url_exists(name) -> bool:
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False
