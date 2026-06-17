"""_player_vs emits --side-tint from the player color, omits it when null."""
from django.template import Context, Template
from django.test import TestCase

from core.user.models import User

TPL = Template('{% include "portal/components/_player_vs.html" %}')


class PlayerVsColorTests(TestCase):
    def setUp(self):
        self.p1 = User.objects.create_user(
            username="alice", email="a@example.com", password="pw-123456789")
        self.p2 = User.objects.create_user(
            username="bob", email="b@example.com", password="pw-123456789")

    def test_emits_side_tint_when_color_set(self):
        ctx = Context({
            "home_player": {"user": self.p1, "name": "alice", "color": "#17B6BE"},
            "away_player": {"user": self.p2, "name": "bob", "color": "#D8453B"},
        })
        html = TPL.render(ctx)
        self.assertIn("--side-tint: #17B6BE", html)
        self.assertIn("--side-tint: #D8453B", html)

    def test_omits_side_tint_when_color_null(self):
        ctx = Context({
            "home_player": {"user": self.p1, "name": "alice", "color": None},
            "away_player": {"user": self.p2, "name": "bob", "color": None},
        })
        html = TPL.render(ctx)
        self.assertNotIn("--side-tint", html)
