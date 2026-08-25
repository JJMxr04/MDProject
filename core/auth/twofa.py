"""Two-factor (TOTP) enrollment + recovery helpers.

Hand-rolled on django-otp primitives — no
``django-two-factor-auth``. One confirmed ``TOTPDevice`` per enrolled user
plus one ``StaticDevice`` holding ten single-use backup codes.

Every state change (enable / disable / regenerate) sends a transactional
security email through the existing ``core.mail.send_email`` task — like a
password reset, it bypasses the ``email_notifications`` preference because a
2FA change is account-security mail the user can't opt out of.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

logger = logging.getLogger(__name__)

TOTP_DEVICE_NAME = "default"
STATIC_DEVICE_NAME = "backup"
BACKUP_CODE_COUNT = 10


# --------------------------------------------------------------------- lookups


def confirmed_totp(user) -> TOTPDevice | None:
    """The user's confirmed TOTP device, or None if 2FA isn't active."""
    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def has_2fa(user) -> bool:
    return confirmed_totp(user) is not None


def get_or_create_unconfirmed_totp(user) -> TOTPDevice:
    """Fetch (or create) the *unconfirmed* enrollment device for ``user``.

    Reused across repeated GETs of the setup page so refreshing doesn't strand
    a pile of half-enrolled devices. If the user already has a confirmed
    device this still returns a fresh unconfirmed one — the caller gates on
    ``has_2fa`` before offering setup.
    """
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(
            user=user, name=TOTP_DEVICE_NAME, confirmed=False,
        )
    return device


def static_device(user) -> StaticDevice | None:
    return StaticDevice.objects.filter(user=user, name=STATIC_DEVICE_NAME).first()


def backup_codes_remaining(user) -> int:
    device = static_device(user)
    return device.token_set.count() if device else 0


# ---------------------------------------------------------------- mutations


@transaction.atomic
def issue_backup_codes(user, count: int = BACKUP_CODE_COUNT) -> list[str]:
    """Replace the user's backup codes with ``count`` fresh single-use codes.

    Returns the plaintext codes so the caller can render them **once** — they
    are not retrievable afterward (django-otp stores them as-is but we never
    surface them again; a lost set is regenerated, not recovered).
    """
    device, _ = StaticDevice.objects.get_or_create(user=user, name=STATIC_DEVICE_NAME)
    device.token_set.all().delete()
    codes = []
    for _ in range(count):
        token = StaticToken.random_token()
        device.token_set.create(token=token)
        codes.append(token)
    return codes


@transaction.atomic
def disable_2fa(user) -> None:
    """Remove every TOTP and backup-code device the user owns."""
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()


# ------------------------------------------------------------------- email


def send_security_email(user, event: str) -> None:
    """Defer a transactional 2FA security email. ``event`` is one of
    ``enabled`` / ``disabled`` / ``regenerated`` / ``password_changed``.

    Best-effort: a mail failure must never block the security action itself,
    so deferral errors are logged and swallowed.
    """
    headlines = {
        "enabled": "Two-factor authentication was enabled",
        "disabled": "Two-factor authentication was disabled",
        "regenerated": "Your backup codes were regenerated",
        "password_changed": "Your password was changed",  # nosec B105 -- user-facing email headline, not a credential
    }
    headline = headlines.get(event, "Your two-factor settings changed")
    try:
        from core.mail.tasks import send_email

        send_email.defer(
            subject=f"{headline} on your Paradise Sports account",
            recipient=user.email,
            template_path="authorization/security_email_2fa.html",
            context={
                "username": getattr(user, "name", None) or user.get_username(),
                "headline": headline,
                "event": event,
                "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
            },
        )
    except Exception:  # noqa: BLE001 — security action must not fail on mail
        logger.exception("2FA security email defer failed for user=%s event=%s", user.pk, event)
