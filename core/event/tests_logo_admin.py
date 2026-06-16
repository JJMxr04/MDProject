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
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.event.admin import TeamAdmin, TeamAdminForm, _store_admin_logo
from core.event.models import League, Sport, Team, TeamLogo
from core.portal.cards import fixture_from_dict


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


class TeamAdminFetchLogoActionTests(TestCase):
    def setUp(self):
        self.sport = Sport.objects.create(id="basketball", name="Basketball")
        self.league = League.objects.create(id="usa-nba", sport=self.sport, name="NBA")
        self.team_missing = Team.objects.create(
            id="usa-nba:38", league=self.league, team_id="38",
            sport=self.sport, name_long="Lakers",
        )
        self.team_ok = Team.objects.create(
            id="usa-nba:39", league=self.league, team_id="39",
            sport=self.sport, name_long="Celtics",
        )
        TeamLogo.objects.create(
            team=self.team_ok, status="ok", source="aggregator", byte_size=10,
        )

    @patch("core.event.admin.fetch_team_logo_task")
    def test_action_enqueues_only_missing_teams(self, mock_task):
        admin_instance = TeamAdmin(Team, None)
        admin_instance.message_user = MagicMock()
        request = MagicMock()
        qs = Team.objects.filter(league=self.league)
        admin_instance.fetch_logo_from_aggregator(request, qs)
        mock_task.defer.assert_called_once_with(team_id="usa-nba:38")
        admin_instance.message_user.assert_called_once()
        report = admin_instance.message_user.call_args.args[1]
        self.assertIn("1", report)

    @patch("core.event.admin.fetch_team_logo_task")
    def test_action_noop_when_all_have_ok_logos(self, mock_task):
        admin_instance = TeamAdmin(Team, None)
        admin_instance.message_user = MagicMock()
        request = MagicMock()
        qs = Team.objects.filter(id="usa-nba:39")
        admin_instance.fetch_logo_from_aggregator(request, qs)
        mock_task.defer.assert_not_called()
        admin_instance.message_user.assert_called_once()


class LogoRoutingAuditTests(TestCase):
    """Routing contract: persisted surfaces serve MDProject's own mirror,
    aggregator surfaces pass the aggregator's logo_url string through verbatim.
    """

    def setUp(self):
        self.sport = Sport.objects.create(id="basketball", name="Basketball")
        self.league = League.objects.create(id="usa-nba", sport=self.sport, name="NBA")
        self.team = Team.objects.create(
            id="usa-nba:38", league=self.league, team_id="38",
            sport=self.sport, name_long="Lakers",
        )

    def test_persisted_team_logo_url_routes_to_mdproject_mirror(self):
        TeamLogo.objects.create(
            team=self.team, status="ok", source="aggregator", byte_size=10,
        )
        self.assertEqual(self.team.logo_url, "/logos/teams/usa-nba:38")

    def test_persisted_team_logo_url_none_when_not_ok(self):
        TeamLogo.objects.create(
            team=self.team, status="missing", source="aggregator", byte_size=0,
        )
        self.assertIsNone(self.team.logo_url)

    def test_persisted_team_logo_url_none_when_no_row(self):
        self.assertIsNone(self.team.logo_url)

    def test_aggregator_fixture_passes_through_logo_url(self):
        # fixture_from_dict reads the aggregator event dict directly — the
        # nested ``home_team``/``away_team`` dicts and their ``logo_url``
        # strings. No MDProject Team is consulted, so whatever URL the
        # aggregator supplies must survive unchanged into the fixture.
        ev = {
            "league": {"name": "NBA"},
            "start_time": "2026-06-16T18:00:00Z",
            "is_live": False,
            "is_finalized": False,
            "home_team": {
                "name": "Lakers",
                "logo_url": "https://cdn.aggrigator.example/logos/home.png",
            },
            "away_team": {
                "name": "Celtics",
                "logo_url": "https://cdn.aggrigator.example/logos/away.png",
            },
            "home_score": None,
            "away_score": None,
        }
        fixture = fixture_from_dict(ev)
        self.assertEqual(
            fixture["home"]["logo_url"],
            "https://cdn.aggrigator.example/logos/home.png",
        )
        self.assertEqual(
            fixture["away"]["logo_url"],
            "https://cdn.aggrigator.example/logos/away.png",
        )
        # Passthrough must NOT route through MDProject's own /logos/teams mirror.
        self.assertNotIn("/logos/teams/", fixture["home"]["logo_url"])
        self.assertNotIn("/logos/teams/", fixture["away"]["logo_url"])

    def test_aggregator_fixture_missing_logo_is_empty_string(self):
        # team_side coerces a missing logo_url to "" so {% if team.logo_url %}
        # falls through to the initials fallback in _team_logo.html.
        ev = {
            "home_team": {"name": "Lakers"},
            "away_team": {"name": "Celtics"},
        }
        fixture = fixture_from_dict(ev)
        self.assertEqual(fixture["home"]["logo_url"], "")
        self.assertEqual(fixture["away"]["logo_url"], "")
