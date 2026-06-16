from django.test import TestCase

from core.user.models import User


class AvatarFieldRetiredTests(TestCase):
    def test_user_has_no_avatar_imagefield(self):
        field_names = {f.name for f in User._meta.get_fields()}
        self.assertNotIn("avatar", field_names)

    def test_avatar_url_still_works(self):
        from core.user.models import UserAvatar
        u = User.objects.create_user(
            username="hank", email="hank@example.com", password="pw-123456789"
        )
        UserAvatar.objects.create(user=u, image=b"x", status="ok", etag="e1")
        self.assertIsNotNone(u.avatar_url)
