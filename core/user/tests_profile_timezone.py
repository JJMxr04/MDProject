"""Settings (UserProfileForm) edits the timezone + clock format."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.user.forms.user.UserProfileForm import UserProfileForm
from core.user.models import User


@override_settings(USE_AGGRIGATOR=False)
class UserProfileTimezoneFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u", email="u@e.com", password="pw"
        )

    def _data(self, **over):
        data = {
            "username": "u",
            "email": "u@e.com",
            "first_name": "U",
            "last_name": "Ser",
            "bio": "",
            "home_color": "",
            "away_color": "",
            "timezone": "America/New_York",
            "clock_format": "24h",
        }
        data.update(over)
        return data

    def test_updates_timezone_and_clock(self):
        form = UserProfileForm(data=self._data(), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "America/New_York")
        self.assertEqual(self.user.clock_format, "24h")

    def test_invalid_timezone_falls_back_to_utc(self):
        form = UserProfileForm(data=self._data(timezone="Nope/Nope"), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "UTC")

    def test_rejects_bogus_clock_format(self):
        # clock_format is a 2-value choices field — tampered values are
        # rejected by the field itself (spec L6, safe by construction).
        form = UserProfileForm(data=self._data(clock_format="banana"), instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("clock_format", form.errors)

    def test_settings_page_exposes_both_controls(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("core-portal:profile"), secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="timezone"')
        self.assertContains(resp, 'name="clock_format"')

    def test_omitting_prefs_preserves_stored_values(self):
        self.user.timezone = "America/New_York"
        self.user.clock_format = "24h"
        self.user.save()
        data = self._data()
        data.pop("timezone")
        data.pop("clock_format")
        form = UserProfileForm(data=data, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.timezone, "America/New_York")
        self.assertEqual(self.user.clock_format, "24h")
