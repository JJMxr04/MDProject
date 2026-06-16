from django.test import TestCase, override_settings
from django.urls import reverse

from core.match.tests.factories import make_user


@override_settings(USE_AGGRIGATOR=False)
class DuelsPageContextTests(TestCase):
    def test_context_has_leaderboard_key(self):
        user = make_user("viewer")
        self.client.force_login(user)
        resp = self.client.get(reverse("core-portal:portal-duels"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("leaderboard", resp.context)
        self.assertIn("duel_record", resp.context)
