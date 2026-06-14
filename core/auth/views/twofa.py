"""Self-service 2FA: enrollment, recovery, and the login second-step (phase 15).

Two entry points share one flow (D-15a): the portal Security rail and the
admin "set up 2FA" banner both link to ``2fa-setup``. Staff are portal users —
one flow, two doors.

Security model:
- Setup confirms against the *specific* unconfirmed device (``verify_token``),
  not ``match_token`` (which only considers confirmed devices).
- Disable / regenerate require a live TOTP or backup code (``match_token``),
  never session state alone — a hijacked session can't strip 2FA.
- The login second step never trusts the client for identity: the pending
  user pk lives server-side in the session with a 5-minute TTL, and the token
  is matched against that user only.
"""

from __future__ import annotations

import io
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_http_methods, require_POST
from django_otp import login as otp_login
from django_otp import match_token

from core.auth import twofa
from core.ratelimit import rate_limit
from core.user.models import User

SESSION_PENDING_KEY = "2fa_pending"
PENDING_TTL = timedelta(minutes=5)


# --------------------------------------------------------------------- helpers


def _qr_svg(data: str) -> str:
    """Render ``data`` as an inline SVG (no external request, CSP-safe).

    The XML prolog is stripped so the ``<svg>`` can be embedded directly in
    the page body.
    """
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    return mark_safe(svg[svg.find("<svg"):])


def _post_login_redirect(user, next_url: str | None):
    if next_url:
        return redirect(next_url)
    if user.is_staff:
        return redirect("core-admin:admin_dashboard")
    return redirect("core-portal:portal-dashboard")


# ----------------------------------------------------------- portal: status


@login_required
def security_view(request):
    """The Security rail page — current 2FA state + enable/disable/regen."""
    device = twofa.confirmed_totp(request.user)
    context = {
        "active": "security",
        "twofa_enabled": device is not None,
        "confirmed_at": device.created_at if device else None,
        "backup_codes_remaining": twofa.backup_codes_remaining(request.user),
    }
    return render(request, "portal/security/index.html", context)


# ----------------------------------------------------------- portal: setup


@login_required
@require_http_methods(["GET", "POST"])
def setup_view(request):
    """GET: show QR + manual key + confirm form. POST: confirm the code,
    mark the device confirmed, issue backup codes, and show them once."""
    if twofa.has_2fa(request.user):
        # Already enrolled — nothing to set up. Send them to the status page.
        return redirect("core-auth:2fa-security")

    device = twofa.get_or_create_unconfirmed_totp(request.user)

    if request.method == "POST":
        token = (request.POST.get("otp_token") or "").strip()
        if device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            codes = twofa.issue_backup_codes(request.user)
            twofa.send_security_email(request.user, "enabled")
            return render(
                request,
                "portal/security/backup_codes.html",
                {"active": "security", "codes": codes, "context_event": "enabled"},
            )
        messages.error(request, "That code didn't match. Check your authenticator app and try again.")

    return render(
        request,
        "portal/security/setup.html",
        {
            "active": "security",
            "qr_svg": _qr_svg(device.config_url),
            "manual_key": device.key,
        },
    )


@login_required
@require_POST
def disable_view(request):
    """Turn 2FA off. Requires a live TOTP or backup code (not session only)."""
    if not twofa.has_2fa(request.user):
        return redirect("core-auth:2fa-security")

    token = (request.POST.get("otp_token") or "").strip()
    if token and match_token(request.user, token):
        twofa.disable_2fa(request.user)
        twofa.send_security_email(request.user, "disabled")
        messages.success(request, "Two-factor authentication is now off.")
        return redirect("core-auth:2fa-security")

    messages.error(request, "Enter a current code from your authenticator app (or a backup code) to turn 2FA off.")
    return redirect("core-auth:2fa-security")


@login_required
@require_POST
def regenerate_view(request):
    """Issue a fresh set of backup codes. Requires a live code; old codes die."""
    if not twofa.has_2fa(request.user):
        return redirect("core-auth:2fa-security")

    token = (request.POST.get("otp_token") or "").strip()
    if token and match_token(request.user, token):
        codes = twofa.issue_backup_codes(request.user)
        twofa.send_security_email(request.user, "regenerated")
        return render(
            request,
            "portal/security/backup_codes.html",
            {"active": "security", "codes": codes, "context_event": "regenerated"},
        )

    messages.error(request, "Enter a current code to regenerate your backup codes.")
    return redirect("core-auth:2fa-security")


# ------------------------------------------------------- login second step


@rate_limit("2fa-verify", 10, 3600)
@require_http_methods(["GET", "POST"])
def verify_view(request):
    """Second login step for enrolled users. The first step (LoginView) put
    the pending user pk in the session; here we match a token against it.

    django-axes only sees ``authenticate()`` (the password step), so token
    failures are invisible to it — the ``@rate_limit`` above is the brake.
    """
    if request.user.is_authenticated:
        return _post_login_redirect(request.user, None)

    pending = request.session.get(SESSION_PENDING_KEY)
    if not pending:
        return redirect("core-auth:login")

    started = timezone.datetime.fromisoformat(pending["ts"])
    if timezone.now() - started > PENDING_TTL:
        request.session.pop(SESSION_PENDING_KEY, None)
        messages.error(request, "Your sign-in timed out. Please log in again.")
        return redirect("core-auth:login")

    if request.method == "POST":
        user = User.objects.filter(pk=pending["user_pk"]).first()
        token = (request.POST.get("otp_token") or "").strip()
        device = match_token(user, token) if (user and token) else None
        if device:
            next_url = pending.get("next")
            # Multiple auth backends are configured, so login() needs an
            # explicit one. Use whichever vouched for the password step; fall
            # back to the model backend (axes never authenticates by itself).
            backend = pending.get("backend") or settings.AUTHENTICATION_BACKENDS[-1]
            auth_login(request, user, backend=backend)
            otp_login(request, device)  # marks the session OTP-verified
            request.session.pop(SESSION_PENDING_KEY, None)
            return _post_login_redirect(user, next_url)
        messages.error(request, "That code didn't match. Try again, or use a backup code.")

    return render(request, "authorization/twofa_verify.html", {})
