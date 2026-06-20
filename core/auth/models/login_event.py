"""Per-user login security records (device, IP, approximate country, time).

Two tables on purpose (see spec): ``LoginEvent`` holds forensic detail with a
90-day retention; ``KnownLoginFingerprint`` is a small, long-lived baseline
(no IP) used to decide whether a login is from a new device or country. Keeping
the baseline separate means we can purge the detailed PII rows without losing
the ability to flag "new device/location".
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class LoginEvent(models.Model):
    SUCCESS = "success"
    FAILED = "failed"
    LOGOUT = "logout"
    EVENT_TYPES = [
        (SUCCESS, "Successful login"),
        (FAILED, "Failed login"),
        (LOGOUT, "Logout"),
    ]

    # CASCADE: a deleted account takes its security log with it (privacy).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.CASCADE,
        related_name="login_events",
    )
    event_type = models.CharField(max_length=16, choices=EVENT_TYPES, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    country = models.CharField(max_length=2, blank=True)
    user_agent = models.TextField(blank=True)
    device_label = models.CharField(max_length=128, blank=True)
    # Lets us revoke this exact session later. Same trust level as
    # django_session, which already stores the key as its primary key.
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    is_new_device = models.BooleanField(default=False)
    is_new_location = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        who = self.user_id or "anon"
        return f"{self.event_type} {who} {self.device_label} {self.country} @ {self.created_at:%Y-%m-%d %H:%M}"


class KnownLoginFingerprint(models.Model):
    """Baseline of (country, device) pairs a user has logged in from before.
    No IP — country + device family only. Never age-purged."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_fingerprints",
    )
    country = models.CharField(max_length=2, blank=True)
    device_label = models.CharField(max_length=128, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "country", "device_label"],
                name="uniq_user_country_device",
            ),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.device_label}:{self.country}"
