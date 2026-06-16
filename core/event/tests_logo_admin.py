"""Admin logo-upload tests: validate + re-encode → TeamLogo DB row.

Tests cover:
1. clean_logo_upload returns WEBP bytes for a valid image.
2. An invalid file (not an image) is rejected.
3. Missing upload is a no-op (None, no error).
4. save_model end-to-end: writes a TeamLogo row with status=ok, content_type=image/webp.
5. _store_admin_logo helper persistence.
6. Manual upload overwrites a pre-existing 'missing' row.
"""

import io
from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.event.admin import TeamAdmin, TeamAdminForm, _store_admin_logo
from core.event.models import League, Sport, Team, TeamLogo


def _img_upload(name, fmt, content_type):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (5, 6, 7)).save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def _minimal_team_data(team):
    """Build a data dict that satisfies Team's required ModelForm fields."""
    return {
        "id": team.id,
        "team_id": team.team_id,
        "league": team.league_id,
        "sport": team.sport_id,
        "name_long": team.name_long,
        "name_medium": "",
        "name_short": "",
        "stat_entity_id": "",
        "primary_color": "",
        "secondary_color": "",
        "primary_contrast": "",
        "secondary_contrast": "",
    }


class TeamAdminLogoUploadTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        self.team = Team.objects.create(
            id="usa-nba:38",
            league=league,
            team_id="38",
            sport=sport,
            name_long="Lakers",
        )

    def test_valid_logo_is_reencoded_to_webp_bytes(self):
        form = TeamAdminForm(
            data=_minimal_team_data(self.team),
            files={"logo_upload": _img_upload("logo.png", "PNG", "image/png")},
            instance=self.team,
        )
        self.assertTrue(form.is_valid(), form.errors)
        result = form.cleaned_data["logo_upload"]
        self.assertIsInstance(result, (bytes, bytearray))
        # WEBP magic bytes: RIFF....WEBP
        self.assertTrue(result[:4] == b"RIFF" and result[8:12] == b"WEBP")

    def test_invalid_file_rejected(self):
        bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        form = TeamAdminForm(
            data=_minimal_team_data(self.team),
            files={"logo_upload": bad},
            instance=self.team,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("logo_upload", form.errors)

    def test_missing_upload_is_noop(self):
        form = TeamAdminForm(
            data=_minimal_team_data(self.team),
            files={},
            instance=self.team,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data.get("logo_upload"))

    def test_save_model_writes_team_logo_row(self):
        form = TeamAdminForm(
            data=_minimal_team_data(self.team),
            files={"logo_upload": _img_upload("crest.png", "PNG", "image/png")},
            instance=self.team,
        )
        self.assertTrue(form.is_valid(), form.errors)

        admin_instance = TeamAdmin(Team, None)
        request = MagicMock()
        # change=True: team already exists, save_model just calls obj.save().
        admin_instance.save_model(request, self.team, form, change=True)

        logo = TeamLogo.objects.get(team=self.team)
        self.assertEqual(logo.status, "ok")
        self.assertEqual(logo.content_type, "image/webp")
        self.assertEqual(logo.source, "admin")
        self.assertGreater(logo.byte_size, 0)
        self.assertIsNotNone(logo.image)
        self.assertEqual(logo.byte_size, len(bytes(logo.image)))

    def test_store_admin_logo_helper_directly(self):
        """_store_admin_logo persists arbitrary bytes with the right metadata."""
        fake_bytes = b"\x00" * 64
        _store_admin_logo(self.team, fake_bytes)

        logo = TeamLogo.objects.get(team=self.team)
        self.assertEqual(logo.status, "ok")
        self.assertEqual(logo.source, "admin")
        self.assertEqual(logo.content_type, "image/webp")
        self.assertEqual(logo.byte_size, len(fake_bytes))

    def test_store_admin_logo_overwrites_existing_missing_row(self):
        """A manual upload overwrites a pre-existing 'missing' aggregator row."""
        TeamLogo.objects.create(
            team=self.team,
            status="missing",
            source="aggregator",
            byte_size=0,
        )
        fake_bytes = b"\x00" * 64
        _store_admin_logo(self.team, fake_bytes)

        logo = TeamLogo.objects.get(team=self.team)
        self.assertEqual(logo.status, "ok")
        self.assertEqual(logo.source, "admin")
