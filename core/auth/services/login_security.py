"""Pure-ish helpers behind the login-security signals. Kept out of the signal
module so they unit-test without faking signal dispatch."""

from __future__ import annotations

import logging

from django.conf import settings
from django.template.defaultfilters import date as date_filter
from django.utils import timezone

from core.auth.models import KnownLoginFingerprint, LoginEvent
from core.ip import get_client_ip
from core.mail.tasks import send_email  # module-level so tests can patch it

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


def _send_new_login_alert(user, event):
    """Email the user about a sign-in from a new device or country.
    Best-effort: a mail failure must never break the login."""
    try:
        # Procrastinate serializes defer() args to JSON, so the context must be
        # JSON-safe — pre-format the timestamp to a string here, never pass the
        # datetime through.
        when_display = (
            date_filter(event.created_at, "M j, Y \\a\\t H:i") if event.created_at else ""
        )
        send_email.defer(
            subject="New sign-in to your Paradise Sports account",
            recipient=user.email,
            template_path="authorization/security_email_new_login.html",
            context={
                "headline": "New sign-in to your account",
                "username": getattr(user, "name", None) or user.get_username(),
                "device_label": event.device_label or "an unrecognized device",
                "country": event.country or "an unknown location",
                "when_display": when_display,
                "is_new_device": event.is_new_device,
                "is_new_location": event.is_new_location,
                "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("new-login alert defer failed for user=%s", getattr(user, "pk", None))


def record_login_event(user, request):
    """Write a SUCCESS LoginEvent for this login. Best-effort: never raises."""
    try:
        ua = request.META.get("HTTP_USER_AGENT", "")
        country = (request.META.get("HTTP_CF_IPCOUNTRY", "") or "").strip()[:2]
        device_label = summarize_user_agent(ua)
        is_new_device, is_new_location = upsert_fingerprint(user, country, device_label)
        session_key = getattr(getattr(request, "session", None), "session_key", None)
        event = LoginEvent.objects.create(
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
        if is_new_device or is_new_location:
            _send_new_login_alert(user, event)
        return event
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


def _user_session_keys(user):
    return set(
        LoginEvent.objects
        .filter(user=user, session_key__isnull=False)
        .exclude(session_key="")
        .values_list("session_key", flat=True)
    )


def revoke_other_sessions(user, keep_session_key=None) -> int:
    """Delete all DB sessions this user has logged in from, except
    ``keep_session_key``. Returns the number deleted."""
    from django.contrib.sessions.models import Session

    keys = _user_session_keys(user)
    keys.discard(keep_session_key)
    if not keys:
        return 0
    deleted, _ = Session.objects.filter(session_key__in=keys).delete()
    return deleted


def revoke_all_sessions(user) -> int:
    """Delete every DB session this user has logged in from."""
    return revoke_other_sessions(user, keep_session_key=None)


def _session_belongs_to(session, user_pk_str: str) -> bool:
    """True if a decoded DB session is authenticated as ``user_pk_str``.
    Guards against showing/revoking a session_key that's been recycled to a
    different user since we logged it."""
    try:
        return session.get_decoded().get("_auth_user_id") == user_pk_str
    except Exception:  # noqa: BLE001 — a corrupt session is simply "not ours"
        return False


def active_sessions_for_user(user, current_session_key=None) -> list[dict]:
    """Live (non-expired) DB sessions this user is currently signed in on,
    enriched with the device/country/time from the login that created them.

    Only sessions we have a SUCCESS LoginEvent for are listed (that's where the
    device label comes from), and each is re-confirmed against the decoded
    session so a recycled key can't surface under the wrong account."""
    from django.contrib.sessions.models import Session

    uid = str(user.pk)
    keys = _user_session_keys(user)
    if not keys:
        return []

    # Most-recent SUCCESS event per session_key → device/country/time.
    events: dict[str, LoginEvent] = {}
    for ev in (
        LoginEvent.objects
        .filter(user=user, event_type=LoginEvent.SUCCESS, session_key__in=keys)
        .order_by("-created_at")
    ):
        events.setdefault(ev.session_key, ev)

    rows = []
    live = Session.objects.filter(session_key__in=keys, expire_date__gte=timezone.now())
    for session in live:
        if not _session_belongs_to(session, uid):
            continue
        ev = events.get(session.session_key)
        rows.append({
            "session_key": session.session_key,
            "is_current": session.session_key == current_session_key,
            "device_label": getattr(ev, "device_label", "") or "Unknown device",
            "country": getattr(ev, "country", "") or "",
            "ip_address": getattr(ev, "ip_address", None),
            "last_login_at": getattr(ev, "created_at", None),
            "expires_at": session.expire_date,
        })

    # Current device first, then most-recent login.
    rows.sort(
        key=lambda r: (
            not r["is_current"],
            -(r["last_login_at"].timestamp() if r["last_login_at"] else 0),
        )
    )
    return rows


def revoke_session(user, session_key: str) -> bool:
    """Sign out a single device: delete one DB session, but only if it really
    belongs to ``user``. Returns True if a session was deleted."""
    from django.contrib.sessions.models import Session

    if not session_key:
        return False
    session = Session.objects.filter(session_key=session_key).first()
    if session is None or not _session_belongs_to(session, str(user.pk)):
        return False
    session.delete()
    return True


def recent_activity_for_user(user, limit: int = 20):
    """Recent security-relevant events for the portal: successful and failed
    sign-ins. Logout events are excluded — they aren't actionable for the user."""
    return (
        LoginEvent.objects
        .filter(user=user)
        .exclude(event_type=LoginEvent.LOGOUT)[:limit]
    )
