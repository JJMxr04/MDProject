import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.user.models import User, UserAvatar
from core.user.serializers import UserSerializer, UserMeSerializer


def _png_upload(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class UserSerializerAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="gail", email="gail@example.com", password="pw-123456789"
        )

    def test_write_persists_to_useravatar_bytea(self):
        ser = UserSerializer(self.user, data={"avatar": _png_upload()}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        row = UserAvatar.objects.get(pk=self.user.pk)
        self.assertEqual(row.status, "ok")
        self.assertEqual(row.content_type, "image/webp")
        self.assertEqual(bytes(row.image)[:4], b"RIFF")

    def test_read_exposes_avatar_url_string(self):
        UserAvatar.objects.create(user=self.user, image=b"x", status="ok", etag="e1")
        data = UserSerializer(self.user).data
        self.assertEqual(data["avatar"], self.user.avatar_url)
        self.assertIn(self.user.public_id.hex, data["avatar"])

    def test_read_avatar_null_when_absent(self):
        data = UserMeSerializer(self.user).data
        self.assertIsNone(data["avatar"])

    def test_polyglot_neutralized_via_api(self):
        buf = io.BytesIO()
        Image.new("RGB", (32, 32)).save(buf, format="PNG")
        poly = SimpleUploadedFile("p.png", buf.getvalue() + b"<?php evil(); ?>", content_type="image/png")
        ser = UserSerializer(self.user, data={"avatar": poly}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        row = UserAvatar.objects.get(pk=self.user.pk)
        self.assertNotIn(b"<?php", bytes(row.image))
