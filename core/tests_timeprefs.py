"""Tests for core.timeprefs — timezone normalization, the clock-format
thread-local, and the time-context managers that back both the request
middleware and email rendering."""
from django.test import SimpleTestCase
from django.utils import timezone

from core import timeprefs


class NormalizeTimezoneTests(SimpleTestCase):
    def test_valid_iana_zone_passes_through(self):
        self.assertEqual(
            timeprefs.normalize_timezone("America/New_York"), "America/New_York"
        )

    def test_unknown_zone_falls_back_to_utc(self):
        self.assertEqual(timeprefs.normalize_timezone("Mars/Phobos"), "UTC")

    def test_path_traversal_attempt_falls_back_to_utc(self):
        # Security M4: validation is allowlist membership, never ZoneInfo()
        # construction, so a filesystem-style key never resolves.
        self.assertEqual(timeprefs.normalize_timezone("../../etc/passwd"), "UTC")

    def test_blank_and_none_fall_back_to_utc(self):
        self.assertEqual(timeprefs.normalize_timezone(""), "UTC")
        self.assertEqual(timeprefs.normalize_timezone(None), "UTC")


class NormalizeClockFormatTests(SimpleTestCase):
    def test_valid_values_pass_through(self):
        self.assertEqual(timeprefs.normalize_clock_format("12h"), "12h")
        self.assertEqual(timeprefs.normalize_clock_format("24h"), "24h")

    def test_unknown_value_falls_back_to_12h(self):
        self.assertEqual(timeprefs.normalize_clock_format("banana"), "12h")
        self.assertEqual(timeprefs.normalize_clock_format(None), "12h")


class ClockFormatThreadLocalTests(SimpleTestCase):
    def tearDown(self):
        timeprefs.deactivate_clock_format()

    def test_default_is_12h(self):
        self.assertEqual(timeprefs.get_clock_format(), "12h")

    def test_activate_then_get(self):
        timeprefs.activate_clock_format("24h")
        self.assertEqual(timeprefs.get_clock_format(), "24h")

    def test_deactivate_resets_to_default(self):
        timeprefs.activate_clock_format("24h")
        timeprefs.deactivate_clock_format()
        self.assertEqual(timeprefs.get_clock_format(), "12h")


class TimeContextTests(SimpleTestCase):
    def tearDown(self):
        timezone.deactivate()
        timeprefs.deactivate_clock_format()

    def test_activates_timezone_and_clock(self):
        with timeprefs.time_context("America/New_York", "24h"):
            self.assertEqual(
                timezone.get_current_timezone_name(), "America/New_York"
            )
            self.assertEqual(timeprefs.get_clock_format(), "24h")

    def test_restores_state_on_exit(self):
        with timeprefs.time_context("America/New_York", "24h"):
            pass
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        self.assertEqual(timeprefs.get_clock_format(), "12h")

    def test_restores_state_even_when_body_raises(self):
        # Security H3: no bleed across requests/jobs sharing a worker thread.
        with self.assertRaises(ValueError):
            with timeprefs.time_context("America/New_York", "24h"):
                raise ValueError("boom")
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        self.assertEqual(timeprefs.get_clock_format(), "12h")

    def test_bad_timezone_does_not_raise(self):
        # Security H2: a bad stored value must never 500 the request.
        with timeprefs.time_context("Mars/Phobos", "12h"):
            self.assertEqual(timezone.get_current_timezone_name(), "UTC")
