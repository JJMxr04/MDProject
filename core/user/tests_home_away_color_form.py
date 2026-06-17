"""Profile form persists/validates home_color + away_color."""
from django.test import TestCase
from django.urls import reverse

from core.user.models import User


class ProfileColorFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cara", email="cara@example.com", password="pw-123456789"
        )
        self.client.force_login(self.user)
        self.url = reverse("core-portal:profile")

    def _base_post(self, **extra):
        data = {
            "username": "cara", "email": "cara@example.com",
            "first_name": "Cara", "last_name": "Example", "bio": "hi",
        }
        data.update(extra)
        return data

    def test_valid_hex_persists(self):
        resp = self.client.post(self.url, self._base_post(
            home_color="#17B6BE", away_color="#D8453B"))
        self.assertIn(resp.status_code, (302, 200))
        self.user.refresh_from_db()
        self.assertEqual(self.user.home_color, "#17B6BE")
        self.assertEqual(self.user.away_color, "#D8453B")

    def test_empty_persists_as_null(self):
        # Pre-set, then clear.
        self.user.home_color = "#000000"
        self.user.save(update_fields=["home_color"])
        resp = self.client.post(self.url, self._base_post(
            home_color="", away_color=""))
        self.assertIn(resp.status_code, (302, 200))
        self.user.refresh_from_db()
        self.assertIsNone(self.user.home_color)
        self.assertIsNone(self.user.away_color)

    def test_invalid_hex_rejected(self):
        resp = self.client.post(self.url, self._base_post(
            home_color="not-a-color", away_color="#D8453B"))
        # Form invalid → re-render (200), nothing persisted.
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.home_color)
