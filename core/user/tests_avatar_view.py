from django.test import TestCase
from django.urls import reverse

from core.user.models import User, UserAvatar


class AvatarServeViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="carol", email="carol@example.com", password="pw-123456789"
        )
        self.target = User.objects.create_user(
            username="dave", email="dave@example.com", password="pw-123456789"
        )
        self.row = UserAvatar.objects.create(
            user=self.target, image=b"WEBPBYTES", content_type="image/webp",
            byte_size=9, etag="abc123", status="ok",
        )
        self.url = reverse("user-avatar", kwargs={"public_id": self.target.public_id.hex})

    def test_anonymous_is_blocked(self):
        resp = self.client.get(self.url)
        self.assertIn(resp.status_code, (302, 401, 403))
        self.assertNotEqual(resp.status_code, 200)

    def test_authenticated_gets_bytes_and_etag(self):
        self.client.force_login(self.owner)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/webp")
        self.assertEqual(resp["ETag"], '"abc123"')
        self.assertEqual(resp.content, b"WEBPBYTES")

    def test_304_on_matching_if_none_match(self):
        self.client.force_login(self.owner)
        resp = self.client.get(self.url, HTTP_IF_NONE_MATCH='"abc123"')
        self.assertEqual(resp.status_code, 304)
        self.assertEqual(resp["ETag"], '"abc123"')

    def test_404_when_status_missing(self):
        self.client.force_login(self.owner)
        self.row.status = "missing"
        self.row.save(update_fields=["status"])
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 404)

    def test_404_for_unknown_public_id(self):
        import uuid
        self.client.force_login(self.owner)
        url = reverse("user-avatar", kwargs={"public_id": uuid.uuid4().hex})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
