"""User.timezone / User.clock_format storage + defaults."""
from django.test import TestCase, override_settings

from core.user.models import User


@override_settings(USE_AGGRIGATOR=False)
class UserTimezonePrefsTests(TestCase):
    def _make(self, **kwargs):
        return User.objects.create_user(
            username="tzuser", email="tz@example.com", password="pw", **kwargs
        )

    def test_defaults_to_utc_and_12h(self):
        user = self._make()
        user.refresh_from_db()
        self.assertEqual(user.timezone, "UTC")
        self.assertEqual(user.clock_format, "12h")

    def test_stores_chosen_preferences(self):
        user = self._make(timezone="America/New_York", clock_format="24h")
        user.refresh_from_db()
        self.assertEqual(user.timezone, "America/New_York")
        self.assertEqual(user.clock_format, "24h")
