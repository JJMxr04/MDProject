"""Self-service password change for signed-in users (Security page Password tab).

Requires the current password (``PasswordChangeForm``), so a hijacked session
alone cannot rotate the password. On success the current session is preserved
via ``update_session_auth_hash`` while every other session's auth hash is
invalidated — other devices are signed out on their next request.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from core.auth.twofa import send_security_email
from core.auth.views.twofa import _security_context
from core.ratelimit import rate_limit


@login_required
@rate_limit("auth-pwchange", 10, 3600, per="user")
@require_http_methods(["GET", "POST"])
def password_change_view(request):
    """POST: change the password from the Security page Password tab.
    GET: nothing to show on its own — send users to the tab."""
    tab_url = reverse("core-auth:2fa-security") + "?tab=password"
    if request.method == "GET":
        return redirect(tab_url)

    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        form.save()
        # Keep this session signed in; other sessions are invalidated by the
        # auth-hash rotation Django performs on password change.
        update_session_auth_hash(request, request.user)
        send_security_email(request.user, "password_changed")
        messages.success(request, "Your password has been changed.")
        return redirect(tab_url)

    messages.error(request, "Please fix the errors below to change your password.")
    return render(request, "portal/security/index.html", _security_context(request, form, active_tab="password"))
