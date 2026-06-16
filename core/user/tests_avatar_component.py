from django.template import Context, Template
from django.test import TestCase

from core.user.models import User, UserAvatar

TPL = Template('{% include "portal/components/_avatar.html" %}')


class AvatarComponentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="frank", email="frank@example.com", password="pw-123456789"
        )

    def test_renders_initials_when_no_avatar(self):
        html = TPL.render(Context({"user": self.user}))
        self.assertIn("avatar__initials", html)
        self.assertNotIn("<img", html)

    def test_renders_img_when_avatar_url_present(self):
        UserAvatar.objects.create(user=self.user, image=b"x", status="ok", etag="e1")
        html = TPL.render(Context({"user": self.user}))
        self.assertIn("<img", html)
        self.assertIn(self.user.avatar_url, html)
