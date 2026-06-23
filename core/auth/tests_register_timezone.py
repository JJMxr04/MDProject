"""Signup captures the (browser-auto-detected) timezone, validated to UTC on
anything missing or bogus."""
from django.test import TestCase, override_settings
from django.urls import reverse

from core.auth.forms.register_form import RegisterForm
from core.auth.models.waitlist import WaitlistEntry


@override_settings(USE_AGGRIGATOR=False)
class RegisterTimezoneTests(TestCase):
    EMAIL = "newbie@example.com"

    def setUp(self):
        WaitlistEntry.objects.create(
            email=self.EMAIL, full_name="New Bie", admin_granted_access=True
        )

    def _data(self, **over):
        data = {
            "username": "newbie",
            "email": self.EMAIL,
            "first_name": "New",
            "last_name": "Bie",
            "date_of_birth": "1990-01-01",
            "password1": "Sup3r!Stng_pw42",
            "password2": "Sup3r!Stng_pw42",
            "age_confirmation": True,
            "timezone": "America/New_York",
        }
        data.update(over)
        return data

    def test_valid_timezone_is_saved(self):
        form = RegisterForm(data=self._data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().timezone, "America/New_York")

    def test_invalid_timezone_falls_back_to_utc(self):
        form = RegisterForm(data=self._data(timezone="Mars/Phobos"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().timezone, "UTC")

    def test_missing_timezone_falls_back_to_utc(self):
        data = self._data()
        data.pop("timezone")
        form = RegisterForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().timezone, "UTC")

    def test_signup_page_renders_autodetect_select(self):
        resp = self.client.get(reverse("core-auth:register"), secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "data-timezone-detect")
        self.assertContains(resp, "America/New_York")
        self.assertContains(resp, "timezone-detect.js")
