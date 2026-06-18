# Login & Device Security Activity — Design

**Date:** 2026-06-18
**Status:** Approved (brainstorming) — pending implementation plan
**Project:** MDProject (`core/auth`)

## Problem

A user can currently log in to MDProject but has no way to see *where* and *on
what* their account has been accessed, and no signal when someone else signs in.
We want a per-user login-security record — device, IP, approximate location, and
time per login — so a user can spot and respond to access they did not authorize
("I'm in one spot and someone else just logged into my account").

## Existing infrastructure (reused, not rebuilt)

- **`core/ip.py::get_client_ip`** — Cloudflare-aware real-client-IP resolver
  (CF-Connecting-IP → last XFF hop → REMOTE_ADDR). Already used by axes.
- **Cloudflare in front** — every request carries `CF-IPCountry`; gives
  country-level geolocation for free, no GeoIP DB or external API.
- **`user_logged_in` signal** — already used in `core/metrics/signals.py`; the
  proven hook pattern for "on login, do X".
- **`django-axes`** — brute-force lockout (failure counting, IP-keyed). We do not
  duplicate this; we add a *user-visible record*, which axes does not provide.
- **`django-otp`** — 2FA. Login flow already routes 2FA users through a verify
  step before `user_logged_in` fires, so events record the *completed* login.
- **Database-backed sessions** (Django default; no `SESSION_ENGINE` override) —
  makes session enumeration and "log out everywhere" feasible via `django_session`.
- **No password-only JWT obtain route** (asserted by `core/auth/tests_twofa.py`) —
  all interactive human logins go through the browser `LoginView` and fire
  `user_logged_in`. API/JWT is therefore out of scope: nothing to track there.
- **Procrastinate `core.mail.tasks.send_email`** — existing async email path for
  alerts.
- **`core/crons`** (`tasks.py` pattern) — existing place for scheduled retention.

## Non-goals

- City-level / lat-long geolocation (country only — decided; no new dependency).
- Tracking API/JWT access (no such login route exists).
- Replacing or reconfiguring axes / 2FA.
- Real-time anomaly scoring / ML. Detection is "new device or new country for
  this user", nothing fancier.

## Decisions (settled during brainstorming)

| # | Decision |
|---|----------|
| D-1 | Full scope, built in three tiers: (1) log + visible history, (2) new-login email alerts, (3) active-session control. |
| D-2 | Country-level geolocation via the `CF-IPCountry` header. No GeoIP DB, no external API. |
| D-3 | Two-table split: `LoginEvent` (forensic detail, short retention) + `KnownLoginFingerprint` (lightweight baseline, long-lived, no IP). |
| D-4 | Detail retention = **90 days**; fingerprints persist. |
| D-5 | In-house lightweight implementation, no new dependencies (Approach A). |
| D-6 | Privacy policy updated as an explicit deliverable (legitimate-interest basis: account security). |
| D-7 | Also log failed login attempts (`user_login_failed`) so "someone is trying" is visible, not just successful logins. |

## Architecture

All new code lives in the `core/auth` app (alongside 2FA and lockout, which are
the same security domain). New files:

- `core/auth/models/login_event.py` — `LoginEvent`, `KnownLoginFingerprint`.
- `core/auth/signals.py` — receivers for `user_logged_in`, `user_logged_out`,
  `user_login_failed`. Registered in `core/auth/apps.py` `ready()`.
- `core/auth/services/login_security.py` — pure helpers: device-label
  summarizer, fingerprint upsert + new-device/new-location computation, session
  revocation. Kept out of the signal so they are unit-testable in isolation.
- `core/auth/views/security_activity.py` — portal page + actions.
- `core/auth/admin.py` — read-only `LoginEvent` admin (extend existing).
- `core/crons/tasks.py` — `purge_login_events` retention task (extend existing).
- Email template under the activation/mail template tree.
- Edit `core/web/templates/public/privacyPolicy.html`.

### Data model

`LoginEvent` (detail; CASCADE on user delete — purge with the account):

| field | type | notes |
|-------|------|-------|
| `user` | FK(AUTH_USER_MODEL, CASCADE) | |
| `event_type` | CharField choices | `success` / `failed` / `logout` |
| `ip_address` | GenericIPAddressField, null | from `get_client_ip` |
| `country` | CharField(2), blank | from `CF-IPCountry` (`XX`/blank when absent) |
| `user_agent` | TextField, blank | raw UA string |
| `device_label` | CharField | derived, e.g. "Chrome on macOS" |
| `session_key` | CharField, null, indexed | enables targeted revoke; same trust level as `django_session` (which stores it as PK) |
| `is_new_device` | bool | computed at write |
| `is_new_location` | bool | computed at write |
| `created_at` | DateTimeField(auto_now_add, indexed) | |

Indexes: `(user, created_at)`, `(event_type, created_at)`.

`KnownLoginFingerprint` (baseline; **no IP**, long-lived):

| field | type | notes |
|-------|------|-------|
| `user` | FK(AUTH_USER_MODEL, CASCADE) | |
| `country` | CharField(2), blank | |
| `device_label` | CharField | |
| `first_seen` | DateTimeField | drives "is this new?" |
| `last_seen` | DateTimeField | |

Unique together: `(user, country, device_label)`.

### Write path (signals)

`user_logged_in`:
1. Resolve `ip = get_client_ip(request)`, `country = request.META.get("HTTP_CF_IPCOUNTRY", "")`, `device_label = summarize_user_agent(request.META.get("HTTP_USER_AGENT",""))`.
2. `is_new = upsert_fingerprint(user, country, device_label)` → returns whether device and/or country were previously unseen for this user, and refreshes `last_seen`.
3. Create `LoginEvent(success, ..., session_key=request.session.session_key, is_new_device, is_new_location)`.
4. If `is_new_device or is_new_location`: enqueue alert email (tier 2).
5. Entire body wrapped in `try/except` that logs and swallows — **a logging
   failure must never block a login** (same discipline as `metrics.track`).

`user_logged_out`: write a `logout` event for the ending session (best-effort).

`user_login_failed`: write a `failed` event (no session). Credentials map to a
user when the username/email resolves; otherwise `user` is null-tolerated or the
event is attributed by the attempted identifier in `props`-style fields. (Exact
attribution rule pinned in the implementation plan.)

### Device-label summarizer

Pure function, no dependency: lower-cased substring/regex match over the UA for
the common browser families (Chrome, Edge, Firefox, Safari, Opera, plus
"app"/bot fallthrough) and OS families (Windows, macOS, iOS, Android, Linux).
Returns `"{browser} on {os}"`, or `"Unknown device"` when nothing matches. Goal
is human-recognizable, not exhaustive fingerprinting.

### Alerts (tier 2)

On a `success` event flagged new-device/new-location, defer `send_email` with a
"New sign-in to your account" template: device, country, time, and a link to the
security page with a prominent "This wasn't me" path. Because the fingerprint is
upserted *before* the alert check, the alert only fires the first time a given
(country, device) is seen — no spam on repeat logins from the same device.

### Session control (tier 3)

- **Portal page** `core-auth:security-activity`: lists recent `LoginEvent`s
  (device, location, time), new-device/location badges, highlights the current
  session (`request.session.session_key`), shows active sessions (events whose
  `session_key` still exists and is unexpired in `django_session`).
- **"Log out everywhere else"**: delete every `django_session` row whose key
  matches this user's `LoginEvent.session_key` set, except the current one.
- **"This wasn't me"**: log out everywhere (including current) + force a password
  reset (reuse existing `core/auth/views/password_reset.py` flow) + optionally
  set an axes lock. Confirmation step required.
- All state-changing actions are POST + CSRF; Alpine wiring follows the portal's
  CSP constraints (bare dotted paths, args via `:data-*`).

### Admin

Register `LoginEvent` read-only (no add/change/delete) with list filters on
`event_type`, `country`, `is_new_device`, and search by user. For staff incident
review; complements the axes admin (which shows lockouts, not history).

### Retention + privacy (tier 1)

- `core/crons` task `purge_login_events`: delete `LoginEvent` rows older than 90
  days. `KnownLoginFingerprint` is never purged by age (no PII beyond country +
  device family; needed for detection). Scheduled like existing crons.
- **Privacy policy**: add a "Login & device security" subsection to
  `privacyPolicy.html` disclosing: collection of IP address, approximate location
  (country), and device/browser info; purpose = account security and fraud
  detection (legitimate interest); 90-day retention of detailed records; and that
  users can review this activity in their account. The portal page itself is the
  transparency mechanism.

## Data flow

```
login form ──► LoginView (+2FA verify) ──► auth_login ──► user_logged_in signal
                                                              │
        get_client_ip ─┐  CF-IPCountry ─┐  HTTP_USER_AGENT ─┐ │
                       ▼                ▼                    ▼ ▼
                 upsert_fingerprint(user, country, device) ──► is_new?
                       │                                        │
                       ▼                                        ▼
                 LoginEvent.create(...) ───────────► if new: send_email.defer (alert)

portal "Security activity" ──► list LoginEvents / active sessions
                            ├─► "log out everywhere" ─► delete other django_session rows
                            └─► "this wasn't me"      ─► logout-all + password reset (+ axes lock)

cron purge_login_events (daily) ──► delete LoginEvent older than 90d (keep fingerprints)
```

## Error handling

- Signal body never raises into the auth flow (try/except + `logger.exception`).
- Missing `CF-IPCountry` (local dev / direct origin hit) → blank country; not
  treated as a "new location" on its own (blank ≠ a new country code).
- Missing/blank UA → `"Unknown device"`; not auto-flagged as new device on every
  hit (an all-blank fingerprint is matched like any other).
- Session revocation tolerates already-expired/missing session rows.

## Testing (TDD)

Unit:
- `summarize_user_agent` across representative UA strings + blank/garbage.
- `upsert_fingerprint`: first-seen flags true; second-seen flags false;
  new country vs known device and vice-versa; `last_seen` refresh.
- Country read from `HTTP_CF_IPCOUNTRY`; IP read via `get_client_ip` (CF header).

Integration:
- `user_logged_in` writes one `success` event with correct fields + session_key.
- New device/location → alert `send_email` deferred exactly once; repeat login
  from same device → no alert.
- `user_login_failed` writes a `failed` event.
- Signal swallows a forced write error without breaking the login response.
- "Log out everywhere else" deletes other sessions, keeps current.
- "This wasn't me" triggers logout-all + password-reset path.
- `purge_login_events` deletes >90d events, retains fingerprints and recent events.

(Note: image/storage-style tests elsewhere need a FileSystemStorage override; not
relevant here — no file writes.)

## Build order (tiers → increments)

1. **Tier 1** — models + migration, signals (success/logout/failed), device
   summarizer, fingerprint logic, portal read-only activity page, admin,
   retention cron, privacy-policy edit. Ships the visible history.
2. **Tier 2** — new-login alert email + template, deferred from the signal.
3. **Tier 3** — active-session list, "log out everywhere else", "this wasn't me".

Each tier is independently shippable and testable.
