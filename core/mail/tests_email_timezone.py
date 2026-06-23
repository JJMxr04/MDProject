"""Emails render every datetime in the recipient's timezone + clock format,
resolved from their stored prefs at send time (zero changes at call sites)."""
import copy
import os
import tempfile
from datetime import datetime
from datetime import timezone as dttz

from django.conf import settings
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from core import timeprefs
from core.user.models import User

# A temp template dir holding a tiny fixture that renders a time via usertime.
_TMP = tempfile.mkdtemp()
with open(os.path.join(_TMP, "tz_fixture.html"), "w") as _f:
    _f.write("{% load usertime %}<p>{{ dt|usertime:'datetime' }}</p>")

_TEMPLATES = copy.deepcopy(settings.TEMPLATES)
_TEMPLATES[0]["DIRS"] = list(_TEMPLATES[0]["DIRS"]) + [_TMP]

# 19:00 UTC = 15:00 in America/New_York (EDT) in June.
DT = datetime(2026, 6, 22, 19, 0, tzinfo=dttz.utc)


@override_settings(USE_AGGRIGATOR=False)
class RecipientTimeContextTests(TestCase):
    def tearDown(self):
        timezone.deactivate()
        timeprefs.deactivate_clock_format()

    def test_uses_recipient_stored_prefs(self):
        from core.mail.tasks import recipient_time_context

        User.objects.create_user(
            username="r", email="r@e.com", password="pw",
            timezone="America/New_York", clock_format="24h",
        )
        with recipient_time_context("r@e.com"):
            self.assertEqual(timezone.get_current_timezone_name(), "America/New_York")
            self.assertEqual(timeprefs.get_clock_format(), "24h")

    def test_unknown_recipient_defaults_to_utc_12h(self):
        from core.mail.tasks import recipient_time_context

        with recipient_time_context("nobody@e.com"):
            self.assertEqual(timezone.get_current_timezone_name(), "UTC")
            self.assertEqual(timeprefs.get_clock_format(), "12h")


@override_settings(
    USE_AGGRIGATOR=False,
    TEMPLATES=_TEMPLATES,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class SendEmailLocalizationTests(TestCase):
    def test_send_email_localizes_body_to_recipient(self):
        from core.mail.tasks import send_email

        User.objects.create_user(
            username="r", email="r@e.com", password="pw",
            timezone="America/New_York", clock_format="24h",
        )
        send_email("Subj", "r@e.com", "tz_fixture.html", {"dt": DT})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Jun 22, 2026 15:00", mail.outbox[0].body)

    def test_send_email_restores_state_after_send(self):
        from core.mail.tasks import send_email

        send_email("Subj", "nobody@e.com", "tz_fixture.html", {"dt": DT})
        # No bleed onto the worker thread afterwards.
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        self.assertEqual(timeprefs.get_clock_format(), "12h")
