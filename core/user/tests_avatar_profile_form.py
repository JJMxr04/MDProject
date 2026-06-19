import hashlib
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from core.user.models import User, UserAvatar


def _png_upload(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class ProfileAvatarUploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="erin", email="erin@example.com", password="pw-123456789"
        )
        self.client.force_login(self.user)
        self.url = reverse("core-portal:profile")

    def test_upload_persists_webp_bytes_to_useravatar(self):
        resp = self.client.post(self.url, {
            "username": "erin", "email": "erin@example.com",
            "first_name": "Erin", "last_name": "Example", "bio": "hi",
            "avatar_upload": _png_upload(),
        })
        self.assertIn(resp.status_code, (302, 200))
        row = UserAvatar.objects.get(pk=self.user.pk)
        self.assertEqual(row.status, "ok")
        self.assertEqual(row.source, "upload")
        self.assertEqual(row.content_type, "image/webp")
        self.assertGreater(row.byte_size, 0)
        self.assertEqual(row.etag, hashlib.sha256(bytes(row.image)).hexdigest()[:32])
        self.assertEqual(bytes(row.image)[:4], b"RIFF")
        self.assertEqual(bytes(row.image)[8:12], b"WEBP")

    def test_polyglot_is_neutralized(self):
        buf = io.BytesIO()
        Image.new("RGB", (32, 32)).save(buf, format="PNG")
        poly = SimpleUploadedFile("p.png", buf.getvalue() + b"<?php evil(); ?>", content_type="image/png")
        self.client.post(self.url, {
            "username": "erin", "email": "erin@example.com",
            "first_name": "Erin", "last_name": "Example", "bio": "x",
            "avatar_upload": poly,
        })
        row = UserAvatar.objects.get(pk=self.user.pk)
        self.assertNotIn(b"<?php", bytes(row.image))

    def test_no_avatar_upload_leaves_row_absent(self):
        self.client.post(self.url, {
            "username": "erin", "email": "erin@example.com",
            "first_name": "Erin", "last_name": "Example", "bio": "x",
        })
        self.assertFalse(UserAvatar.objects.filter(pk=self.user.pk).exists())
