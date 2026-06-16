from django.test import TestCase, override_settings
from django.urls import reverse

from core.match.tests.factories import make_match, make_user


@override_settings(USE_AGGRIGATOR=False)
class MyMatchListTests(TestCase):
    def test_each_match_has_outcome_attached(self):
        p1 = make_user("p1")
        p2 = make_user("p2")
        make_match(p1, p2, accept=True)
        self.client.force_login(p1)
        resp = self.client.get(reverse("core-portal:portal-my-match-list"))
        self.assertEqual(resp.status_code, 200)
        match = resp.context["matches"].object_list[0]
        self.assertIn(match.outcome["state"], {"pending", "won", "lost", "draw"})
