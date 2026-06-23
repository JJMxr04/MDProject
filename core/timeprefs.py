"""Per-user time preferences: timezone normalization, the clock-format
thread-local, and the context managers that activate both.

The web path activates these per request (TimezonePreferenceMiddleware); the
email path activates them per render (core.mail.tasks). Both go through
``time_context`` so activation is uniformly defensive (a bad stored value
never raises — Security H2) and always restored (no cross-request/cross-job
bleed on a reused worker thread — Security H3).
"""
import datetime as _datetime
import threading
from contextlib import contextmanager
from functools import lru_cache
from zoneinfo import available_timezones

from django.utils import timezone
from django.utils.dateformat import format as _dateformat

DEFAULT_TIMEZONE = "UTC"
DEFAULT_CLOCK_FORMAT = "12h"
CLOCK_FORMATS = ("12h", "24h")

# Format strings keyed by style; the time half swaps on the active clock format.
# Single source of truth for both the {% usertime %} filter and any server-side
# serializer that ships a pre-formatted *_display string to JS (the client never
# localizes — backend is authoritative).
_DATE_FMT = "M j, Y"
_TIME_FMT = {"12h": "g:i A", "24h": "H:i"}


def format_datetime(value, style="datetime") -> str:
    """Render ``value`` in the active timezone + clock format.

    ``style`` is ``"date"``, ``"time"``, or ``"datetime"``. Aware datetimes are
    converted to the active zone; naive datetimes and pure ``date`` objects
    (DateFields — no timezone) format as-is. Empty in → empty out.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, _datetime.datetime) and timezone.is_aware(value):
        value = timezone.localtime(value)
    clock = get_clock_format()
    if style == "date":
        fmt = _DATE_FMT
    elif style == "time":
        fmt = _TIME_FMT[clock]
    else:
        fmt = f"{_DATE_FMT} {_TIME_FMT[clock]}"
    return _dateformat(value, fmt)


@lru_cache(maxsize=1)
def _zone_allowlist() -> frozenset:
    # available_timezones() builds a large set by walking the tz database;
    # cache it once so the hot-path validator/middleware never recompute it
    # (Security M4).
    return frozenset(available_timezones())


def normalize_timezone(value) -> str:
    """Return ``value`` only if it is a known IANA zone, else ``"UTC"``.

    Validation is allowlist membership — never ``ZoneInfo(value)`` — so an
    attacker-controlled string can't resolve a filesystem path (Security M4).
    """
    if value and value in _zone_allowlist():
        return value
    return DEFAULT_TIMEZONE


# Surfaced at the top of the timezone dropdown (signup + settings) so the
# common cases are one click away; the full IANA list follows, sorted.
_COMMON_ZONES = (
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Australia/Sydney",
    "UTC",
)


@lru_cache(maxsize=1)
def timezone_choices() -> tuple:
    """``(value, label)`` pairs for a timezone ``<select>`` — common zones
    first, then every IANA zone sorted."""
    common = [(z, z) for z in _COMMON_ZONES if z in _zone_allowlist()]
    rest = [(z, z) for z in sorted(_zone_allowlist()) if z not in _COMMON_ZONES]
    return tuple(common + rest)


def normalize_clock_format(value) -> str:
    """Return ``value`` only if it is a known clock format, else ``"12h"``."""
    if value in CLOCK_FORMATS:
        return value
    return DEFAULT_CLOCK_FORMAT


# --- Clock-format thread-local -------------------------------------------
# Parallel to django.utils.timezone's active-timezone thread-local: the clock
# format can't ride on timezone.activate(), so it gets its own.
_active = threading.local()


def activate_clock_format(value) -> None:
    _active.clock_format = normalize_clock_format(value)


def deactivate_clock_format() -> None:
    if hasattr(_active, "clock_format"):
        del _active.clock_format


def get_clock_format() -> str:
    return getattr(_active, "clock_format", DEFAULT_CLOCK_FORMAT)


@contextmanager
def time_context(tz, clock_format):
    """Activate ``tz`` + ``clock_format`` for the duration of the block.

    Defensive (bad tz → UTC, never raises) and always restored on exit,
    including when the body raises.
    """
    activate_clock_format(clock_format)
    timezone.activate(normalize_timezone(tz))
    try:
        yield
    finally:
        timezone.deactivate()
        deactivate_clock_format()


def user_time_context(user):
    """``time_context`` sourced from a User's stored preferences."""
    return time_context(
        getattr(user, "timezone", DEFAULT_TIMEZONE),
        getattr(user, "clock_format", DEFAULT_CLOCK_FORMAT),
    )
