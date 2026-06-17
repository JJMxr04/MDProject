"""Render tests for the shared player-vs-player hero."""
from django.template import Context, Template
from django.test import TestCase

from core.user.models import User

TPL = Template('{% include "portal/components/_player_vs.html" %}')


class PlayerVsComponentTests(TestCase):
    def setUp(self):
        self.p1 = User.objects.create_user(
            username="alice", email="a@example.com", password="pw-123456789")
        self.p2 = User.objects.create_user(
            username="bob", email="b@example.com", password="pw-123456789")

    def test_renders_both_players(self):
        ctx = Context({
            "home_player": {"user": self.p1, "name": "alice", "sub": "Lv 3", "pick": "Home"},
            "away_player": {"user": self.p2, "name": "bob", "sub": "Lv 2", "pick": "Away"},
        })
        html = TPL.render(ctx)
        self.assertIn("alice", html)
        self.assertIn("bob", html)
        self.assertIn("vs-card__side--home", html)
        self.assertIn("vs-card__side--away", html)
        # Two avatar initials (no avatar_url set → initials path in _avatar).
        self.assertEqual(html.count("avatar__initials"), 2)

    def test_optional_fields_omitted_gracefully(self):
        ctx = Context({
            "home_player": {"user": self.p1, "name": "alice"},
            "away_player": {"user": self.p2, "name": "bob"},
        })
        html = TPL.render(ctx)
        self.assertIn("alice", html)
        self.assertIn("bob", html)
