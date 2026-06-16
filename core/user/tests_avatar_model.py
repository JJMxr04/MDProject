from django.test import TestCase

from core.user.models import User, UserAvatar


class UserAvatarModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="pw-123456789"
        )

    def test_table_name_and_defaults(self):
        self.assertEqual(UserAvatar._meta.db_table, "core_user_avatar")
        row = UserAvatar.objects.create(
            user=self.user, image=b"\x00\x01webpbytes",
            content_type="image/webp", byte_size=10, etag="deadbeef", status="ok",
        )
        self.assertEqual(row.source, "upload")
        self.assertEqual(row.pk, self.user.pk)
        self.assertEqual(self.user.avatar_row.status, "ok")

    def test_one_to_one_reverse_accessor(self):
        UserAvatar.objects.create(user=self.user, status="missing")
        self.assertEqual(self.user.avatar_row.status, "missing")


class UserAvatarUrlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="pw-123456789"
        )

    def test_avatar_url_none_when_no_row(self):
        self.assertIsNone(self.user.avatar_url)

    def test_avatar_url_none_when_missing_status(self):
        UserAvatar.objects.create(user=self.user, status="missing")
        self.assertIsNone(self.user.avatar_url)

    def test_avatar_url_is_public_id_keyed_when_ok(self):
        UserAvatar.objects.create(user=self.user, image=b"x", status="ok", etag="e1")
        url = self.user.avatar_url
        self.assertIsNotNone(url)
        self.assertIn(self.user.public_id.hex, url)
        self.assertNotIn(f"/{self.user.id}", url)
