"""Login-security signal receivers. Registered in apps.AuthConfig.ready().

Each receiver delegates to a best-effort recorder in
core.auth.services.login_security — those swallow their own errors, so a
logging hiccup can never break authentication."""

from __future__ import annotations

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from core.auth.services import login_security


@receiver(user_logged_in)
def on_logged_in(sender, request, user, **kwargs):
    login_security.record_login_event(user, request)


@receiver(user_logged_out)
def on_logged_out(sender, request, user, **kwargs):
    login_security.record_logout(user, request)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    login_security.record_failed_login(credentials, request)
