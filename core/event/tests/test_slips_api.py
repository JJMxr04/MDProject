"""``POST /api/slips`` — parlay combiner output shape.

Specifically: leg labels are the plain-English pick (team names), never the
raw aggregator ``Selection.label`` — which for moneyline is "home home" /
"away away" when the book omits a market name.
"""

from __future__ import annotations

from django.test import override_settings
from rest_framework.test import APITestCase

from core.match.tests.factories import (
    make_event,
    make_league,
    make_two_way_market,
    make_user,
)


@override_settings(USE_AGGRIGATOR=False)
class SlipsLabelTests(APITestCase):
    def setUp(self):
        self.user = make_user("slipper")
        self.client.force_authenticate(user=self.user)
        self.league = make_league()
        self.event = make_event(self.league)
        _, self.home, self.away = make_two_way_market(self.event)

    def test_leg_label_is_humanized(self):
        self.home.label = "home home"
        self.home.save()
        resp = self.client.post(
            "/api/slips",
            {"legs": [{"selection_id": self.home.id}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        leg = resp.json()["legs"][0]
        self.assertEqual(leg["label"], "Home Team Test to win")
        self.assertEqual(leg["type"], "HOME")
