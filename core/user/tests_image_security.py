import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from core.auth.serializers import RegisterSerializer
from core.user.models import User
from core.user.serializers import UserSerializer

# Saving an avatar exercises the storage backend. Prod default is S3 (no creds
# in tests), so route writes to a throwaway local dir for these tests.
_TMP_MEDIA = tempfile.mkdtemp()
_LOCAL_STORAGE = override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    },
    MEDIA_ROOT=_TMP_MEDIA,
)


def _png_upload(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (1, 2, 3)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class RegisterSerializerAvatarTests(TestCase):
    def test_avatar_not_acceptable_at_registration(self):
        # Even if a client sends an avatar, the field must not be writable here.
        self.assertNotIn("avatar", RegisterSerializer().fields)


@_LOCAL_STORAGE
class AuthenticatedAvatarUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="pw-123456789"
        )

    def test_owner_can_set_avatar_and_it_is_reencoded(self):
        ser = UserSerializer(self.user, data={"avatar": _png_upload()}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar.name.endswith(".webp"))

    def test_polyglot_avatar_is_neutralized(self):
        buf = io.BytesIO()
        Image.new("RGB", (32, 32)).save(buf, format="PNG")
        poly = SimpleUploadedFile(
            "p.png", buf.getvalue() + b"<?php evil(); ?>", content_type="image/png"
        )
        ser = UserSerializer(self.user, data={"avatar": poly}, partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        ser.save()
        self.user.refresh_from_db()
        with self.user.avatar.open("rb") as fh:
            self.assertNotIn(b"<?php", fh.read())
