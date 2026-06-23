"""The {% load usertime %} `usertime` filter — renders an aware datetime in
the active timezone + the active clock format."""
from datetime import date, datetime
from datetime import timezone as dttz

from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import timezone

from core import timeprefs
from core.templatetags.usertime import usertime

# 19:00 UTC — 3:00 PM / 15:00 in America/New_York (EDT, UTC-4) in June.
DT = datetime(2026, 6, 22, 19, 0, tzinfo=dttz.utc)


class UserTimeFilterTests(SimpleTestCase):
    def tearDown(self):
        timezone.deactivate()
        timeprefs.deactivate_clock_format()

    def test_datetime_12h(self):
        timeprefs.activate_clock_format("12h")
        self.assertEqual(usertime(DT, "datetime"), "Jun 22, 2026 7:00 PM")

    def test_datetime_24h(self):
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(DT, "datetime"), "Jun 22, 2026 19:00")

    def test_time_only_respects_clock(self):
        timeprefs.activate_clock_format("12h")
        self.assertEqual(usertime(DT, "time"), "7:00 PM")
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(DT, "time"), "19:00")

    def test_date_style_unaffected_by_clock(self):
        timeprefs.activate_clock_format("12h")
        self.assertEqual(usertime(DT, "date"), "Jun 22, 2026")
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(DT, "date"), "Jun 22, 2026")

    def test_converts_to_active_timezone(self):
        timeprefs.activate_clock_format("24h")
        timezone.activate("America/New_York")
        self.assertEqual(usertime(DT, "time"), "15:00")
        self.assertEqual(usertime(DT, "datetime"), "Jun 22, 2026 15:00")

    def test_plain_date_object_renders_without_tz_conversion(self):
        # DateFields have no timezone; localtime() would crash on them.
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(date(2026, 6, 22), "date"), "Jun 22, 2026")

    def test_naive_datetime_renders_as_is(self):
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(datetime(2026, 6, 22, 19, 0), "time"), "19:00")

    def test_empty_value_renders_empty(self):
        self.assertEqual(usertime(None, "datetime"), "")
        self.assertEqual(usertime("", "datetime"), "")

    def test_default_style_is_datetime(self):
        timeprefs.activate_clock_format("24h")
        self.assertEqual(usertime(DT), "Jun 22, 2026 19:00")

    def test_loadable_and_renders_in_template(self):
        timeprefs.activate_clock_format("24h")
        tmpl = Template("{% load usertime %}{{ dt|usertime:'time' }}")
        self.assertEqual(tmpl.render(Context({"dt": DT})), "19:00")
