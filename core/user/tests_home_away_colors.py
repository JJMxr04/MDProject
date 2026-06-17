"""User home_color / away_color fields."""
from django.test import TestCase

from core.user.models import User


class UserHomeAwayColorFieldTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="colu", email="colu@example.com", password="pw-123456789"
        )

    def test_fields_default_null(self):
        self.user.refresh_from_db()
        self.assertIsNone(self.user.home_color)
        self.assertIsNone(self.user.away_color)

    def test_fields_accept_hex(self):
        self.user.home_color = "#17B6BE"
        self.user.away_color = "#D8453B"
        self.user.save(update_fields=["home_color", "away_color"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.home_color, "#17B6BE")
        self.assertEqual(self.user.away_color, "#D8453B")
