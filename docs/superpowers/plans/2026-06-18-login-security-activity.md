# Login & Device Security Activity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each MDProject user a per-login security record (device, IP, approximate country, time), proactive new-login email alerts, and active-session control, so they can detect and respond to unauthorized account access.

**Architecture:** A `user_logged_in` / `user_logged_out` / `user_login_failed` signal receiver writes a `LoginEvent` row and upserts a `KnownLoginFingerprint` (used to flag new device/country). The detailed events have a 90-day retention cron; fingerprints persist. The existing portal Security page gains a "Login & device activity" section with session-revocation actions. Reuses the Cloudflare-aware IP resolver, the existing Procrastinate mail task, and DB-backed sessions.

**Tech Stack:** Django 5.2, `core/auth` app (label `core_auth`), Procrastinate (`@app.periodic` crons + `send_email.defer`), `django-axes` / `django-otp` (already present, not modified), Django default DB sessions, Django `TestCase`.

## Global Constraints

- App label is `core_auth` (not `core_auth.auth`); migrations live in `core/auth/migrations/` (last is `0001_initial`, so next is `0002_*`). Copied verbatim from spec.
- Real client IP MUST come from `core.ip.get_client_ip(request)` — never `REMOTE_ADDR` or leftmost `X-Forwarded-For` directly.
- Country comes ONLY from `request.META.get("HTTP_CF_IPCOUNTRY", "")` — no GeoIP DB, no external API.
- No new third-party dependencies.
- Brand name in all user-facing copy/emails is **"Paradise Sports"** (matches existing 2FA emails).
- Every signal/record/mail body MUST swallow its own exceptions (`try/except` + `logger.exception`) — a logging or mail failure must NEVER break a login or a security action. Same discipline as `core/metrics/models.py::track` and `core/auth/twofa.py::send_security_email`.
- Detailed `LoginEvent` retention = 90 days; `KnownLoginFingerprint` is never age-purged.
- Tests run with `python manage.py test core.auth` and use `@override_settings(USE_AGGRIGATOR=False)` on test classes (matches `tests_twofa.py`).
- Portal action endpoints are POST + CSRF; any Alpine wiring uses bare dotted paths and passes args via `:data-*` (portal CSP constraint).

---

## File Structure

- Create `core/auth/models/login_event.py` — `LoginEvent`, `KnownLoginFingerprint` models.
- Modify `core/auth/models/__init__.py` — export the two models.
- Create `core/auth/services/__init__.py` — package marker.
- Create `core/auth/services/login_security.py` — pure helpers: `summarize_user_agent`, `upsert_fingerprint`, `record_login_event`, `record_failed_login`, `record_logout`, `revoke_other_sessions`, `revoke_all_sessions`.
- Create `core/auth/signals.py` — receivers wiring the Django auth signals to the service helpers.
- Modify `core/auth/apps.py` — import signals in `ready()`.
- Create `core/auth/migrations/0002_loginevent_knownloginfingerprint.py` — generated.
- Modify `core/auth/views/twofa.py::security_view` — add login-activity + session context.
- Create `core/auth/views/security_activity.py` — POST actions (`logout_others`, `not_me`).
- Modify `core/auth/urls.py` — routes for the two actions.
- Modify `core/auth/templates/portal/security/index.html` — login-activity section + action forms.
- Modify `core/auth/admin.py` — read-only `LoginEvent` admin.
- Create `core/auth/templates/authorization/security_email_new_login.html` — alert email body.
- Modify `core/crons/tasks.py` — `purge_login_events` periodic task.
- Modify `core/web/templates/public/privacyPolicy.html` — disclosure subsection.
- Create test files: `core/auth/tests_login_activity.py` (service + signals + retention), `core/auth/tests_session_control.py` (tier 3).

---

## TIER 1 — Log + visible history

### Task 1: Data models + migration

**Files:**
- Create: `core/auth/models/login_event.py`
- Modify: `core/auth/models/__init__.py`
- Create: `core/auth/migrations/0002_loginevent_knownloginfingerprint.py` (generated)
- Test: `core/auth/tests_login_activity.py`

**Interfaces:**
- Produces: `LoginEvent` (fields: `user`, `event_type`, `ip_address`, `country`, `user_agent`, `device_label`, `session_key`, `is_new_device`, `is_new_location`, `created_at`); `LoginEvent.SUCCESS`/`FAILED`/`LOGOUT` string constants. `KnownLoginFingerprint` (fields: `user`, `country`, `device_label`, `first_seen`, `last_seen`).

- [ ] **Step 1: Write the failing test**

In `core/auth/tests_login_activity.py`:

```python
from __future__ import annotations

from django.test import TestCase, override_settings

from core.auth.models import LoginEvent, KnownLoginFingerprint
from core.user.models import User


@override_settings(USE_AGGRIGATOR=False)
class LoginEventModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mia", email="mia@test.local", password="pw",
        )

    def test_login_event_defaults_and_str(self):
        ev = LoginEvent.objects.create(
            user=self.user,
            event_type=LoginEvent.SUCCESS,
            ip_address="203.0.113.7",
            country="US",
            user_agent="Mozilla/5.0",
            device_label="Chrome on macOS",
            session_key="abc123",
        )
        self.assertFalse(ev.is_new_device)
        self.assertFalse(ev.is_new_location)
        self.assertIsNotNone(ev.created_at)
        self.assertIn("success", str(ev))

    def test_fingerprint_unique_per_user_country_device(self):
        KnownLoginFingerprint.objects.create(
            user=self.user, country="US", device_label="Chrome on macOS",
        )
        with self.assertRaises(Exception):
            KnownLoginFingerprint.objects.create(
                user=self.user, country="US", device_label="Chrome on macOS",
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity -v 2`
Expected: FAIL — `ImportError: cannot import name 'LoginEvent'`.

- [ ] **Step 3: Write the models**

In `core/auth/models/login_event.py`:

```python
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
```

In `core/auth/models/__init__.py` (currently empty) add:

```python
from core.auth.models.login_event import LoginEvent, KnownLoginFingerprint  # noqa: F401
```

- [ ] **Step 4: Make the migration**

Run: `python manage.py makemigrations core_auth`
Expected: creates `core/auth/migrations/0002_loginevent_knownloginfingerprint.py` with both models.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity -v 2`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add core/auth/models/login_event.py core/auth/models/__init__.py core/auth/migrations/0002_*.py core/auth/tests_login_activity.py
git commit -m "feat(auth): LoginEvent + KnownLoginFingerprint models"
```

---

### Task 2: Service helpers — UA summarizer + fingerprint upsert

**Files:**
- Create: `core/auth/services/__init__.py` (empty)
- Create: `core/auth/services/login_security.py`
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `LoginEvent`, `KnownLoginFingerprint` (Task 1).
- Produces:
  - `summarize_user_agent(ua: str) -> str` — e.g. `"Chrome on macOS"`, `"Unknown device"` for blank/garbage.
  - `upsert_fingerprint(user, country: str, device_label: str) -> tuple[bool, bool]` — returns `(is_new_device, is_new_location)` and creates/refreshes the fingerprint row. `is_new_device` = no prior fingerprint with this `device_label`; `is_new_location` = no prior fingerprint with this non-blank `country`. Both False on a user's very first ever login (nothing is "new" when there's no baseline).

- [ ] **Step 1: Write the failing test (append to `tests_login_activity.py`)**

```python
from core.auth.services.login_security import summarize_user_agent, upsert_fingerprint


@override_settings(USE_AGGRIGATOR=False)
class UserAgentSummaryTests(TestCase):
    def test_chrome_on_macos(self):
        ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
        self.assertEqual(summarize_user_agent(ua), "Chrome on macOS")

    def test_safari_on_iphone(self):
        ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
        self.assertEqual(summarize_user_agent(ua), "Safari on iOS")

    def test_firefox_on_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        self.assertEqual(summarize_user_agent(ua), "Firefox on Windows")

    def test_blank_is_unknown(self):
        self.assertEqual(summarize_user_agent(""), "Unknown device")
        self.assertEqual(summarize_user_agent("garbage-string"), "Unknown device")


@override_settings(USE_AGGRIGATOR=False)
class FingerprintUpsertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="leo", email="leo@test.local", password="pw",
        )

    def test_first_login_is_not_new(self):
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Chrome on macOS")
        self.assertFalse(new_dev)
        self.assertFalse(new_loc)
        self.assertEqual(KnownLoginFingerprint.objects.filter(user=self.user).count(), 1)

    def test_same_device_again_is_not_new(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Chrome on macOS")
        self.assertFalse(new_dev)
        self.assertFalse(new_loc)
        self.assertEqual(KnownLoginFingerprint.objects.filter(user=self.user).count(), 1)

    def test_new_device_known_country(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "US", "Safari on iOS")
        self.assertTrue(new_dev)
        self.assertFalse(new_loc)

    def test_new_country_known_device(self):
        upsert_fingerprint(self.user, "US", "Chrome on macOS")
        new_dev, new_loc = upsert_fingerprint(self.user, "GB", "Chrome on macOS")
        self.assertTrue(new_dev)   # this (country, device) pair is unseen
        self.assertTrue(new_loc)   # GB never seen before
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity -v 2`
Expected: FAIL — `ModuleNotFoundError: core.auth.services.login_security`.

- [ ] **Step 3: Write the helpers**

Create empty `core/auth/services/__init__.py`. Then `core/auth/services/login_security.py`:

```python
"""Pure-ish helpers behind the login-security signals. Kept out of the signal
module so they unit-test without faking signal dispatch."""

from __future__ import annotations

import logging

from django.utils import timezone

from core.auth.models import KnownLoginFingerprint, LoginEvent

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity -v 2`
Expected: PASS (all UA + fingerprint tests).

- [ ] **Step 5: Commit**

```bash
git add core/auth/services/__init__.py core/auth/services/login_security.py core/auth/tests_login_activity.py
git commit -m "feat(auth): UA summarizer + fingerprint new-device/location detection"
```

---

### Task 3: Record functions + signal wiring

**Files:**
- Modify: `core/auth/services/login_security.py` (add record functions)
- Create: `core/auth/signals.py`
- Modify: `core/auth/apps.py` (register in `ready()`)
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `summarize_user_agent`, `upsert_fingerprint` (Task 2); `core.ip.get_client_ip`.
- Produces:
  - `record_login_event(user, request) -> LoginEvent | None` — resolves IP/country/device, upserts fingerprint, writes a `SUCCESS` event with `session_key`. Swallows all errors (returns `None` on failure). NOTE: alert dispatch is added in Task 8.
  - `record_failed_login(credentials: dict, request) -> None` — writes a `FAILED` event; resolves user from `credentials["username"]` against email-or-username, tolerating no match (`user=None`).
  - `record_logout(user, request) -> None` — writes a `LOGOUT` event for the ending session.

- [ ] **Step 1: Write the failing test (append)**

```python
from unittest.mock import patch
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.test import RequestFactory


@override_settings(USE_AGGRIGATOR=False)
class SignalRecordingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ada", email="ada@test.local", password="pw",
        )
        self.rf = RequestFactory()

    def _req(self, ua="Mozilla/5.0 (Windows NT 10.0) Firefox/121.0", country="US", ip="203.0.113.9"):
        req = self.rf.get("/")
        req.META["HTTP_USER_AGENT"] = ua
        req.META["HTTP_CF_IPCOUNTRY"] = country
        req.META["HTTP_CF_CONNECTING_IP"] = ip
        # RequestFactory has no session; attach a fake with a key.
        class _S:
            session_key = "sess-key-1"
        req.session = _S()
        return req

    def test_login_signal_writes_success_event(self):
        user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
        ev = LoginEvent.objects.get(user=self.user, event_type=LoginEvent.SUCCESS)
        self.assertEqual(ev.country, "US")
        self.assertEqual(ev.ip_address, "203.0.113.9")
        self.assertEqual(ev.device_label, "Firefox on Windows")
        self.assertEqual(ev.session_key, "sess-key-1")

    def test_second_login_new_device_flagged(self):
        user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
        user_logged_in.send(
            sender=self.user.__class__,
            request=self._req(ua="Mozilla/5.0 (iPhone) Safari/604.1"),
            user=self.user,
        )
        latest = LoginEvent.objects.filter(user=self.user, event_type=LoginEvent.SUCCESS).first()
        self.assertTrue(latest.is_new_device)

    def test_failed_login_signal_writes_failed_event(self):
        user_login_failed.send(
            sender=self.user.__class__,
            credentials={"username": "ada@test.local"},
            request=self._req(),
        )
        self.assertTrue(
            LoginEvent.objects.filter(user=self.user, event_type=LoginEvent.FAILED).exists()
        )

    def test_signal_swallows_write_errors(self):
        with patch("core.auth.services.login_security.LoginEvent.objects.create",
                   side_effect=RuntimeError("db down")):
            # Must not raise into the auth flow.
            user_logged_in.send(sender=self.user.__class__, request=self._req(), user=self.user)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity.SignalRecordingTests -v 2`
Expected: FAIL — no event written (signals not wired yet).

- [ ] **Step 3: Add record functions to `login_security.py`**

Append to `core/auth/services/login_security.py`:

```python
from core.ip import get_client_ip


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
```

- [ ] **Step 4: Create the signal receivers**

`core/auth/signals.py`:

```python
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
```

- [ ] **Step 5: Register in `apps.py`**

Modify `core/auth/apps.py` — add a `ready()` method to `AuthConfig`:

```python
    def ready(self):
        # Import for the login-security receiver registration side-effect.
        from core.auth import signals  # noqa: F401
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity.SignalRecordingTests -v 2`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add core/auth/services/login_security.py core/auth/signals.py core/auth/apps.py core/auth/tests_login_activity.py
git commit -m "feat(auth): record login/logout/failed events via auth signals"
```

---

### Task 4: Portal Security page — login-activity section

**Files:**
- Modify: `core/auth/views/twofa.py::security_view`
- Modify: `core/auth/templates/portal/security/index.html`
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `LoginEvent` (Task 1), the current `request.session.session_key`.
- Produces: `security_view` context keys `recent_logins` (queryset, ≤20 most recent for the user) and `current_session_key`.

- [ ] **Step 1: Write the failing test (append)**

```python
from django.urls import reverse


@override_settings(USE_AGGRIGATOR=False)
class SecurityPageActivityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sam", email="sam@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_security_page_lists_recent_logins(self):
        LoginEvent.objects.create(
            user=self.user, event_type=LoginEvent.SUCCESS,
            country="US", device_label="Chrome on macOS",
        )
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Chrome on macOS")
        self.assertContains(resp, "Login &amp; device activity")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity.SecurityPageActivityTests -v 2`
Expected: FAIL — page lacks the activity section / "Chrome on macOS" not present.

- [ ] **Step 3: Add context in `security_view`**

In `core/auth/views/twofa.py::security_view`, extend the `context` dict before `render`:

```python
    from core.auth.models import LoginEvent  # local import: avoids load-order cost
    context["recent_logins"] = LoginEvent.objects.filter(user=request.user)[:20]
    context["current_session_key"] = request.session.session_key
```

- [ ] **Step 4: Add the template section**

In `core/auth/templates/portal/security/index.html`, immediately before the final `{% endblock content %}` (and after the existing 2FA `<section>`), add a new card:

```html
    <section class="card-ui">
        <header class="card-ui__header">
            <h2>Login &amp; device activity</h2>
        </header>
        <div class="card-ui__body">
            <p class="twofa-meta">
                Recent sign-ins to your account. If you see activity you don't
                recognize, use "This wasn't me" to secure your account.
            </p>
            <ul class="login-activity">
                {% for ev in recent_logins %}
                <li class="login-activity__row">
                    <span class="login-activity__device">{{ ev.device_label|default:"Unknown device" }}</span>
                    <span class="login-activity__where">{{ ev.country|default:"—" }} · {{ ev.ip_address|default:"" }}</span>
                    <span class="login-activity__when">{{ ev.created_at|date:"M j, Y H:i" }}</span>
                    <span class="login-activity__type login-activity__type--{{ ev.event_type }}">{{ ev.get_event_type_display }}</span>
                    {% if ev.session_key and ev.session_key == current_session_key %}
                        <span class="twofa-pill twofa-pill--on">This device</span>
                    {% endif %}
                    {% if ev.is_new_device or ev.is_new_location %}
                        <span class="twofa-pill">New {% if ev.is_new_device %}device{% else %}location{% endif %}</span>
                    {% endif %}
                </li>
                {% empty %}
                <li class="twofa-meta">No login activity recorded yet.</li>
                {% endfor %}
            </ul>
            {# Session-control action forms are added in Task 11. #}
        </div>
    </section>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity.SecurityPageActivityTests -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/auth/views/twofa.py core/auth/templates/portal/security/index.html core/auth/tests_login_activity.py
git commit -m "feat(auth): show recent login activity on the portal Security page"
```

---

### Task 5: Read-only admin

**Files:**
- Modify: `core/auth/admin.py`
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `LoginEvent` (Task 1).

- [ ] **Step 1: Write the failing test (append)**

```python
@override_settings(USE_AGGRIGATOR=False)
class LoginEventAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="root", email="root@test.local", password="pw",
        )
        self.client.force_login(self.admin)

    def test_login_event_changelist_is_reachable_and_readonly(self):
        from django.contrib import admin as dj_admin
        from core.auth.models import LoginEvent
        self.assertIn(LoginEvent, dj_admin.site._registry)
        options = dj_admin.site._registry[LoginEvent]
        self.assertFalse(options.has_add_permission(self.client.request))
```

(If `has_add_permission` needs a real request, replace the last two lines with: `req = self.client.get("/admin/").wsgi_request; self.assertFalse(options.has_add_permission(req))`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity.LoginEventAdminTests -v 2`
Expected: FAIL — `LoginEvent` not in admin registry.

- [ ] **Step 3: Register the admin**

In `core/auth/admin.py`, add:

```python
from core.auth.models import LoginEvent


@admin.register(LoginEvent)
class LoginEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "event_type", "device_label",
                    "country", "ip_address", "is_new_device", "is_new_location")
    list_filter = ("event_type", "is_new_device", "is_new_location", "country")
    search_fields = ("user__email", "user__username", "ip_address", "device_label")
    date_hierarchy = "created_at"
    # Forensic record — staff review only, never edit.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity.LoginEventAdminTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/auth/admin.py core/auth/tests_login_activity.py
git commit -m "feat(auth): read-only LoginEvent admin for incident review"
```

---

### Task 6: 90-day retention cron

**Files:**
- Modify: `core/crons/tasks.py`
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `LoginEvent`, `KnownLoginFingerprint` (Task 1).
- Produces: `purge_login_events(timestamp: int)` periodic task; helper `_purge_login_events_older_than(days: int) -> int` (returns deleted count) so the cutoff is testable without the scheduler.

- [ ] **Step 1: Write the failing test (append)**

```python
from datetime import timedelta
from django.utils import timezone


@override_settings(USE_AGGRIGATOR=False)
class RetentionPurgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reta", email="reta@test.local", password="pw",
        )

    def test_purges_old_events_keeps_recent_and_fingerprints(self):
        from core.crons.tasks import _purge_login_events_older_than

        old = LoginEvent.objects.create(user=self.user, event_type=LoginEvent.SUCCESS)
        LoginEvent.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=120)
        )
        recent = LoginEvent.objects.create(user=self.user, event_type=LoginEvent.SUCCESS)
        KnownLoginFingerprint.objects.create(
            user=self.user, country="US", device_label="Chrome on macOS",
        )

        deleted = _purge_login_events_older_than(90)

        self.assertEqual(deleted, 1)
        self.assertFalse(LoginEvent.objects.filter(pk=old.pk).exists())
        self.assertTrue(LoginEvent.objects.filter(pk=recent.pk).exists())
        self.assertEqual(KnownLoginFingerprint.objects.filter(user=self.user).count(), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity.RetentionPurgeTests -v 2`
Expected: FAIL — `_purge_login_events_older_than` not defined.

- [ ] **Step 3: Add the task to `core/crons/tasks.py`**

Append:

```python
from datetime import timedelta as _timedelta

from django.utils import timezone as _timezone


def _purge_login_events_older_than(days: int) -> int:
    """Delete LoginEvent rows older than ``days``. KnownLoginFingerprint is
    intentionally untouched — it's the long-lived detection baseline."""
    from core.auth.models import LoginEvent

    cutoff = _timezone.now() - _timedelta(days=days)
    deleted, _ = LoginEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted


@app.periodic(cron="30 3 * * *")
@app.task(name="core.crons.purge_login_events", queue="default", retry=CRON_RETRY)
def purge_login_events(timestamp: int):
    # 90-day retention on detailed login records (spec D-4). Runs 03:30 daily,
    # off-peak and clear of the midnight match/tournament crons.
    count = _purge_login_events_older_than(90)
    logger.info("purge_login_events: deleted %s rows", count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity.RetentionPurgeTests -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/crons/tasks.py core/auth/tests_login_activity.py
git commit -m "feat(auth): 90-day retention cron for login events"
```

---

### Task 7: Privacy-policy disclosure

**Files:**
- Modify: `core/web/templates/public/privacyPolicy.html`

**Interfaces:** none (content change). No automated test — verified by reading the rendered page.

- [ ] **Step 1: Read the existing policy to match heading structure**

Run: `python - <<'PY'\nprint(open("core/web/templates/public/privacyPolicy.html").read()[:2000])\nPY`
Find the section-heading markup (e.g. `<h2>`/`<h3>` + paragraph) and reuse it verbatim in Step 2.

- [ ] **Step 2: Add the disclosure subsection**

Insert a new section using the SAME heading/paragraph markup the file already uses (substitute the real tags/classes for the placeholders below):

```html
<h2>Login &amp; device security</h2>
<p>
    To protect your account, we record information about each sign-in (and
    failed sign-in attempt): your IP address, an approximate location derived
    from it (country only), the date and time, and your device and browser type.
    We process this information on the basis of our legitimate interest in
    securing accounts and detecting and preventing unauthorized access and fraud.
</p>
<p>
    You can review your recent login activity at any time on your account's
    Security page. We retain the detailed records (including IP address) for
    90 days, after which they are deleted automatically; we keep a minimal,
    non-identifying record of the device types and countries you have signed in
    from so we can recognize new sign-ins and alert you to them.
</p>
```

- [ ] **Step 3: Verify it renders**

Run: `python manage.py check`
Expected: `System check identified no issues`. (Manually load `/privacy` in a browser if convenient to confirm formatting.)

- [ ] **Step 4: Commit**

```bash
git add core/web/templates/public/privacyPolicy.html
git commit -m "docs(privacy): disclose login/device security data collection"
```

---

## TIER 2 — New-login alerts

### Task 8: Alert email on new device/location

**Files:**
- Create: `core/auth/templates/authorization/security_email_new_login.html`
- Modify: `core/auth/services/login_security.py` (call alert from `record_login_event`)
- Test: `core/auth/tests_login_activity.py` (append)

**Interfaces:**
- Consumes: `record_login_event` (Task 3), `core.mail.tasks.send_email`.
- Produces: `_send_new_login_alert(user, event)` — defers `send_email` with template `authorization/security_email_new_login.html`; called from `record_login_event` only when `is_new_device or is_new_location`.

- [ ] **Step 1: Write the failing test (append)**

```python
@override_settings(USE_AGGRIGATOR=False)
class NewLoginAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="nora", email="nora@test.local", password="pw",
        )
        self.rf = RequestFactory()

    def _req(self, ua, country="US", ip="203.0.113.9"):
        req = self.rf.get("/")
        req.META.update({
            "HTTP_USER_AGENT": ua, "HTTP_CF_IPCOUNTRY": country,
            "HTTP_CF_CONNECTING_IP": ip,
        })
        class _S:
            session_key = "k"
        req.session = _S()
        return req

    @patch("core.auth.services.login_security.send_email")
    def test_alert_fires_on_new_device_only_once(self, mock_send):
        ua1 = "Mozilla/5.0 (Windows NT 10.0) Firefox/121.0"
        ua2 = "Mozilla/5.0 (iPhone) Safari/604.1"
        # First ever login: baseline, no alert.
        from core.auth.services.login_security import record_login_event
        record_login_event(self.user, self._req(ua1))
        self.assertEqual(mock_send.defer.call_count, 0)
        # New device → one alert.
        record_login_event(self.user, self._req(ua2))
        self.assertEqual(mock_send.defer.call_count, 1)
        # Same new device again → no second alert.
        record_login_event(self.user, self._req(ua2))
        self.assertEqual(mock_send.defer.call_count, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_login_activity.NewLoginAlertTests -v 2`
Expected: FAIL — `send_email` not imported in module / alert never deferred.

- [ ] **Step 3: Add the alert helper and call it**

In `core/auth/services/login_security.py`, add near the top imports:

```python
from django.conf import settings
```

Add the helper:

```python
def _send_new_login_alert(user, event):
    """Email the user about a sign-in from a new device or country.
    Best-effort: a mail failure must never break the login."""
    try:
        from core.mail.tasks import send_email

        send_email.defer(
            subject="New sign-in to your Paradise Sports account",
            recipient=user.email,
            template_path="authorization/security_email_new_login.html",
            context={
                "username": getattr(user, "name", None) or user.get_username(),
                "device_label": event.device_label or "an unrecognized device",
                "country": event.country or "an unknown location",
                "when": event.created_at,
                "is_new_device": event.is_new_device,
                "is_new_location": event.is_new_location,
                "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("new-login alert defer failed for user=%s", getattr(user, "pk", None))
```

NOTE the test patches `core.auth.services.login_security.send_email`, so also add a module-level import so it exists to patch:

```python
from core.mail.tasks import send_email  # module-level so tests can patch it
```

(Then inside `_send_new_login_alert` use the module-level `send_email` rather than the local import — remove the inner `from core.mail.tasks import send_email`.)

In `record_login_event`, right before `return ...`, capture the created event and fire the alert:

```python
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
```

- [ ] **Step 4: Create the email template**

`core/auth/templates/authorization/security_email_new_login.html` (mirror the structure of `security_email_2fa.html`; minimal body shown):

```html
{% extends "email/_base.html" %}
{% block email_body %}
<h1>New sign-in to your account</h1>
<p>Hi {{ username }},</p>
<p>
    We noticed a new sign-in to your Paradise Sports account from
    <strong>{{ device_label }}</strong>
    {% if country %}in <strong>{{ country }}</strong>{% endif %}
    on {{ when|date:"M j, Y" }} at {{ when|date:"H:i" }} UTC.
</p>
<p>If this was you, you can ignore this email.</p>
<p>
    <strong>If this wasn't you</strong>, go to your account's Security page and
    choose "This wasn't me" to sign out everywhere and reset your password, or
    contact us at {{ support_email }}.
</p>
{% endblock %}
```

(If `security_email_2fa.html` does not extend `email/_base.html`, copy whatever wrapper IT uses instead — match the existing convention.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_login_activity.NewLoginAlertTests -v 2`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/auth/services/login_security.py core/auth/templates/authorization/security_email_new_login.html core/auth/tests_login_activity.py
git commit -m "feat(auth): email alert on sign-in from a new device or location"
```

---

## TIER 3 — Active-session control

### Task 9: Session-revocation service

**Files:**
- Modify: `core/auth/services/login_security.py`
- Test: `core/auth/tests_session_control.py` (create)

**Interfaces:**
- Consumes: `LoginEvent` (Task 1), `django.contrib.sessions.models.Session`.
- Produces:
  - `revoke_other_sessions(user, keep_session_key: str | None) -> int` — deletes every DB `Session` whose key is in this user's `LoginEvent.session_key` set except `keep_session_key`; returns count deleted.
  - `revoke_all_sessions(user) -> int` — same but keeps nothing.

- [ ] **Step 1: Write the failing test**

Create `core/auth/tests_session_control.py`:

```python
from __future__ import annotations

from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta

from core.auth.models import LoginEvent
from core.auth.services.login_security import revoke_other_sessions, revoke_all_sessions
from core.user.models import User


def _make_session(key):
    return Session.objects.create(
        session_key=key, session_data="x",
        expire_date=timezone.now() + timedelta(days=1),
    )


@override_settings(USE_AGGRIGATOR=False)
class SessionRevocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rev", email="rev@test.local", password="pw",
        )
        for k in ("keep", "drop1", "drop2"):
            _make_session(k)
            LoginEvent.objects.create(
                user=self.user, event_type=LoginEvent.SUCCESS, session_key=k,
            )

    def test_revoke_others_keeps_current(self):
        n = revoke_other_sessions(self.user, keep_session_key="keep")
        self.assertEqual(n, 2)
        self.assertTrue(Session.objects.filter(session_key="keep").exists())
        self.assertFalse(Session.objects.filter(session_key="drop1").exists())

    def test_revoke_all(self):
        n = revoke_all_sessions(self.user)
        self.assertEqual(n, 3)
        self.assertFalse(Session.objects.filter(session_key__in=["keep", "drop1", "drop2"]).exists())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_session_control -v 2`
Expected: FAIL — `ImportError: revoke_other_sessions`.

- [ ] **Step 3: Implement the helpers**

Append to `core/auth/services/login_security.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_session_control -v 2`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/auth/services/login_security.py core/auth/tests_session_control.py
git commit -m "feat(auth): session revocation helpers (log out everywhere)"
```

---

### Task 10: Portal action views + URLs

**Files:**
- Create: `core/auth/views/security_activity.py`
- Modify: `core/auth/urls.py`
- Test: `core/auth/tests_session_control.py` (append)

**Interfaces:**
- Consumes: `revoke_other_sessions`, `revoke_all_sessions` (Task 9); existing password-reset flow.
- Produces: URL names `core-auth:logout-others` and `core-auth:security-not-me`, both `@login_required` + `@require_POST`.

- [ ] **Step 1: Write the failing test (append to `tests_session_control.py`)**

```python
from django.urls import reverse


@override_settings(USE_AGGRIGATOR=False)
class SessionControlViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="vic", email="vic@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_logout_others_is_post_only(self):
        resp = self.client.get(reverse("core-auth:logout-others"))
        self.assertEqual(resp.status_code, 405)

    def test_logout_others_revokes_and_redirects(self):
        # Two foreign sessions recorded for this user.
        for k in ("foreignA", "foreignB"):
            _make_session(k)
            LoginEvent.objects.create(
                user=self.user, event_type=LoginEvent.SUCCESS, session_key=k,
            )
        resp = self.client.post(reverse("core-auth:logout-others"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Session.objects.filter(session_key="foreignA").exists())

    def test_not_me_logs_out_and_redirects_to_password_reset(self):
        resp = self.client.post(reverse("core-auth:security-not-me"))
        self.assertEqual(resp.status_code, 302)
        # Session flushed → user no longer authenticated.
        self.assertNotIn("_auth_user_id", self.client.session)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_session_control.SessionControlViewTests -v 2`
Expected: FAIL — `NoReverseMatch: 'logout-others'`.

- [ ] **Step 3: Write the views**

`core/auth/views/security_activity.py`:

```python
"""Portal session-control actions on the Security page (tier 3)."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core.auth.services.login_security import (
    revoke_all_sessions,
    revoke_other_sessions,
)


@login_required
@require_POST
def logout_others(request):
    """Sign out every other session for this user; keep the current one."""
    n = revoke_other_sessions(request.user, keep_session_key=request.session.session_key)
    messages.success(request, f"Signed out of {n} other session{'' if n == 1 else 's'}.")
    return redirect("core-auth:2fa-security")


@login_required
@require_POST
def not_me(request):
    """'This wasn't me': revoke every session (including this one) and send the
    user into the password-reset flow to lock the intruder out."""
    user = request.user
    revoke_all_sessions(user)
    auth_logout(request)  # flush the current session too
    return redirect(reverse("core-auth:password_reset")
                    if _url_exists("core-auth:password_reset")
                    else "core-auth:login")


def _url_exists(name) -> bool:
    from django.urls import NoReverseMatch, reverse
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False
```

NOTE: confirm the actual password-reset URL name in `core/auth/urls.py` / `password_reset.py` and replace `"core-auth:password_reset"` with the real name; if password reset lives on Django's default auth URLs, use that name. The `_url_exists` guard keeps the test green even if the name differs (falls back to login).

- [ ] **Step 4: Wire the URLs**

In `core/auth/urls.py`, add imports + routes:

```python
from core.auth.views import security_activity
```

```python
    path('security/logout-others/', security_activity.logout_others, name='logout-others'),
    path('security/not-me/', security_activity.not_me, name='security-not-me'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_session_control.SessionControlViewTests -v 2`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add core/auth/views/security_activity.py core/auth/urls.py core/auth/tests_session_control.py
git commit -m "feat(auth): log-out-everywhere and 'this wasn't me' portal actions"
```

---

### Task 11: Wire action buttons into the Security page

**Files:**
- Modify: `core/auth/templates/portal/security/index.html`
- Test: `core/auth/tests_session_control.py` (append)

**Interfaces:**
- Consumes: URL names from Task 10.

- [ ] **Step 1: Write the failing test (append)**

```python
@override_settings(USE_AGGRIGATOR=False)
class SecurityPageActionsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wes", email="wes@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_action_forms_render(self):
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, reverse("core-auth:logout-others"))
        self.assertContains(resp, reverse("core-auth:security-not-me"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.auth.tests_session_control.SecurityPageActionsRenderTests -v 2`
Expected: FAIL — action URLs not present in the page.

- [ ] **Step 3: Add the action forms**

In `core/auth/templates/portal/security/index.html`, replace the
`{# Session-control action forms are added in Task 11. #}` placeholder (from Task 4) with:

```html
            <div class="login-activity__actions">
                <form method="post" action="{% url 'core-auth:logout-others' %}">
                    {% csrf_token %}
                    <button type="submit" class="btn btn--secondary">
                        Sign out of all other sessions
                    </button>
                </form>
                <form method="post" action="{% url 'core-auth:security-not-me' %}"
                      onsubmit="return confirm('This signs you out everywhere and starts a password reset. Continue?');">
                    {% csrf_token %}
                    <button type="submit" class="btn btn--danger">This wasn't me</button>
                </form>
            </div>
```

(If inline `onsubmit` is blocked by CSP, follow the portal pattern: bind an Alpine `@submit` confirm via a bare dotted path instead — see the portal-Alpine-CSP memory. Match whatever the other portal forms do.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test core.auth.tests_session_control.SecurityPageActionsRenderTests -v 2`
Expected: PASS.

- [ ] **Step 5: Full-suite regression check**

Run: `python manage.py test core.auth -v 1`
Expected: all auth tests pass (new + existing 2FA/lockout/ratelimit suites).

- [ ] **Step 6: Commit**

```bash
git add core/auth/templates/portal/security/index.html core/auth/tests_session_control.py
git commit -m "feat(auth): session-control action buttons on Security page"
```

---

## Self-Review

**Spec coverage:**
- Tier 1 (log + visible history) → Tasks 1–7. ✓
- Tier 2 (new-login alerts) → Task 8. ✓
- Tier 3 (active-session control) → Tasks 9–11. ✓
- Two-table split (D-3) → Task 1. ✓
- Country via CF-IPCountry (D-2) → Tasks 3, used throughout. ✓
- 90-day retention, fingerprints persist (D-4) → Task 6. ✓
- Failed-login logging (D-7) → Task 3. ✓
- Privacy-policy disclosure (D-6) → Task 7. ✓
- No new dependencies (D-5) → no `requirements.txt` change anywhere. ✓
- Best-effort error swallowing → enforced in Tasks 3, 8 record/alert functions. ✓

**Placeholder scan:** No "TBD"/"implement later". Two spots require the implementer to confirm an existing name against the codebase (the email base-template name in Task 8; the password-reset URL name in Task 10) — both are explicit, guarded instructions with verified fallbacks, not blanks.

**Type consistency:** `record_login_event` / `record_failed_login` / `record_logout`, `summarize_user_agent`, `upsert_fingerprint(-> (bool,bool))`, `revoke_other_sessions(user, keep_session_key) -> int`, `revoke_all_sessions(user) -> int`, `_purge_login_events_older_than(days) -> int` are used with identical names/signatures across the tasks that define and consume them. URL names `logout-others` / `security-not-me` match between Task 10 (define) and Task 11 (consume). ✓
