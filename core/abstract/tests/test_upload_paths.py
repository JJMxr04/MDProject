import re
import uuid

from django.test import SimpleTestCase

from core.event.models.team import logo_upload_path
from core.user.models import user_avatar_upload_path

UUID_WEBP = re.compile(r"^[0-9a-f]{32}\.webp$")


class _FakeUser:
    public_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    username = "../../etc/passwd"  # hostile; must be ignored


class _FakeTeam:
    league_id = "EPL"
    team_id = "ARSENAL"


class AvatarPathTests(SimpleTestCase):
    def test_ignores_username_and_filename(self):
        path = user_avatar_upload_path(_FakeUser(), "../../evil.php")
        self.assertTrue(path.startswith("avatars/12345678123456781234567812345678/"))
        self.assertTrue(UUID_WEBP.match(path.rsplit("/", 1)[-1]))
        self.assertNotIn("evil", path)
        self.assertNotIn("passwd", path)


class LogoPathTests(SimpleTestCase):
    def test_ignores_client_filename(self):
        path = logo_upload_path(_FakeTeam(), "../../evil.svg")
        self.assertTrue(path.startswith("teamLogos/EPL/ARSENAL/"))
        self.assertTrue(UUID_WEBP.match(path.rsplit("/", 1)[-1]))
        self.assertNotIn("evil", path)
