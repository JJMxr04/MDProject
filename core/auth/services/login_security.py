"""Pure-ish helpers behind the login-security signals. Kept out of the signal
module so they unit-test without faking signal dispatch."""

from __future__ import annotations

import logging

from django.utils import timezone

from core.auth.models import KnownLoginFingerprint, LoginEvent
from core.ip import get_client_ip

logger = logging.getLogger(__name__)

# Ordered: first match wins. Substrings checked against a lower-cased UA.
# Edge before Chrome (Edge UAs contain "chrome"); Chrome before Safari.
_BROWSERS = [
    ("edg", "Edge"),
    ("opr", "Opera"),
    ("firefox", "Firefox"),
    ("chrome", "Chrome"),
    ("crios", "Chrome"),
    ("fxios", "Firefox"),
    ("safari", "Safari"),
]
# iOS before macOS ("iphone" UAs also say "mac os x"); Android before Linux.
_OSES = [
    ("iphone", "iOS"),
    ("ipad", "iOS"),
    ("android", "Android"),
    ("windows", "Windows"),
    ("mac os x", "macOS"),
    ("macintosh", "macOS"),
    ("linux", "Linux"),
]


def summarize_user_agent(ua: str) -> str:
    """Human-recognizable '{Browser} on {OS}' label. Not a fingerprint."""
    s = (ua or "").lower()
    browser = next((name for token, name in _BROWSERS if token in s), None)
    os_name = next((name for token, name in _OSES if token in s), None)
    if browser and os_name:
        return f"{browser} on {os_name}"
    if browser:
        return browser
    if os_name:
        return os_name
    return "Unknown device"


def upsert_fingerprint(user, country: str, device_label: str) -> tuple[bool, bool]:
    """Record this (country, device) for the user and report whether the
    device and/or country were previously unseen. On the user's very first
    login nothing is 'new' (no baseline to compare against)."""
    had_any = KnownLoginFingerprint.objects.filter(user=user).exists()
    is_new_device = had_any and not KnownLoginFingerprint.objects.filter(
        user=user, device_label=device_label,
    ).exists()
    is_new_location = bool(country) and had_any and not KnownLoginFingerprint.objects.filter(
        user=user, country=country,
    ).exists()

    obj, created = KnownLoginFingerprint.objects.get_or_create(
        user=user, country=country, device_label=device_label,
    )
    if not created:
        obj.last_seen = timezone.now()
        obj.save(update_fields=["last_seen"])
    return is_new_device, is_new_location


def _resolve_user_from_credentials(credentials: dict):
    from core.user.models import User
    ident = (credentials or {}).get("username") or (credentials or {}).get("email")
    if not ident:
        return None
    return (
        User.objects.filter(email__iexact=ident).first()
        or User.objects.filter(username__iexact=ident).first()
    )


def record_login_event(user, request):
    """Write a SUCCESS LoginEvent for this login. Best-effort: never raises."""
    try:
        ua = request.META.get("HTTP_USER_AGENT", "")
        country = (request.META.get("HTTP_CF_IPCOUNTRY", "") or "").strip()[:2]
        device_label = summarize_user_agent(ua)
        is_new_device, is_new_location = upsert_fingerprint(user, country, device_label)
        session_key = getattr(getattr(request, "session", None), "session_key", None)
        return LoginEvent.objects.create(
            user=user,
            event_type=LoginEvent.SUCCESS,
            ip_address=get_client_ip(request),
            country=country,
            user_agent=ua,
            device_label=device_label,
            session_key=session_key,
            is_new_device=is_new_device,
            is_new_location=is_new_location,
        )
    except Exception:  # noqa: BLE001 — logging must never block a login
        logger.exception("record_login_event failed")
        return None


def record_failed_login(credentials, request):
    """Write a FAILED LoginEvent. Best-effort: never raises."""
    try:
        ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
        country = ((request.META.get("HTTP_CF_IPCOUNTRY", "") if request else "") or "").strip()[:2]
        LoginEvent.objects.create(
            user=_resolve_user_from_credentials(credentials),
            event_type=LoginEvent.FAILED,
            ip_address=get_client_ip(request) if request else None,
            country=country,
            user_agent=ua,
            device_label=summarize_user_agent(ua),
        )
    except Exception:  # noqa: BLE001
        logger.exception("record_failed_login failed")


def record_logout(user, request):
    """Write a LOGOUT LoginEvent. Best-effort: never raises."""
    try:
        if user is None or not getattr(user, "pk", None):
            return
        ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
        session_key = getattr(getattr(request, "session", None), "session_key", None)
        LoginEvent.objects.create(
            user=user,
            event_type=LoginEvent.LOGOUT,
            ip_address=get_client_ip(request) if request else None,
            user_agent=ua,
            device_label=summarize_user_agent(ua),
            session_key=session_key,
        )
    except Exception:  # noqa: BLE001
        logger.exception("record_logout failed")
