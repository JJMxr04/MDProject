"""TimezonePreferenceMiddleware activates each authenticated user's timezone +
clock format for the request, and always restores afterwards."""
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from core import timeprefs
from core.middleware.timezone_preference import TimezonePreferenceMiddleware
from core.user.models import User


class TimezonePreferenceMiddlewareTests(SimpleTestCase):
    def tearDown(self):
        timezone.deactivate()
        timeprefs.deactivate_clock_format()

    def _run(self, user):
        captured = {}

        def get_response(request):
            captured["tz"] = timezone.get_current_timezone_name()
            captured["clock"] = timeprefs.get_clock_format()
            return HttpResponse()

        request = RequestFactory().get("/")
        request.user = user
        TimezonePreferenceMiddleware(get_response)(request)
        return captured

    def test_authenticated_user_activates_their_prefs(self):
        user = User(timezone="America/New_York", clock_format="24h")
        captured = self._run(user)
        self.assertEqual(captured["tz"], "America/New_York")
        self.assertEqual(captured["clock"], "24h")

    def test_anonymous_user_keeps_defaults(self):
        captured = self._run(AnonymousUser())
        self.assertEqual(captured["tz"], "UTC")
        self.assertEqual(captured["clock"], "12h")

    def test_invalid_stored_timezone_does_not_500(self):
        # Security H2 — bad value falls back to UTC instead of raising.
        captured = self._run(User(timezone="Mars/Phobos", clock_format="12h"))
        self.assertEqual(captured["tz"], "UTC")

    def test_state_restored_after_request(self):
        # Security H3 — no bleed onto the next request on this worker thread.
        self._run(User(timezone="America/New_York", clock_format="24h"))
        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
        self.assertEqual(timeprefs.get_clock_format(), "12h")
