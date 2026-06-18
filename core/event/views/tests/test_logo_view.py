"""GET /logos/teams/{id}: local hit, 304, and aggregator fallback on miss."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from core.event.models import League, Sport, Team, TeamLogo
from core.event.providers.aggregator_client import (
    AggrigatorError,
    AggrigatorRateLimited,
)


class LogoViewTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        self.team = Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )

    def _url(self, team_id):
        return reverse("team-logo", kwargs={"team_id": team_id})

    def _patch_client(self, **kwargs):
        """Patch the AggrigatorClient the view constructs; configure the
        return/side_effect of get_team_logo_bytes via kwargs."""
        client = mock.Mock()
        client.get_team_logo_bytes.configure_mock(**kwargs)
        return mock.patch(
            "core.event.views.logos.AggrigatorClient", return_value=client
        )

    # ---- local hit (mirrored team) ---------------------------------------

    def test_hit(self):
        TeamLogo.objects.create(
            team=self.team, image=b"PNGDATA", content_type="image/png",
            byte_size=7, etag="abc123", status="ok",
        )
        resp = self.client.get(self._url("usa-nba:38"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "image/png")
        self.assertEqual(resp["ETag"], '"abc123"')
        self.assertEqual(bytes(resp.content), b"PNGDATA")

    def test_304(self):
        TeamLogo.objects.create(
            team=self.team, image=b"PNGDATA", content_type="image/png",
            byte_size=7, etag="abc123", status="ok",
        )
        resp = self.client.get(self._url("usa-nba:38"), HTTP_IF_NONE_MATCH='"abc123"')
        self.assertEqual(resp.status_code, 304)

    def test_local_hit_does_not_call_aggregator(self):
        TeamLogo.objects.create(
            team=self.team, image=b"PNGDATA", content_type="image/png",
            byte_size=7, etag="abc123", status="ok",
        )
        with self._patch_client(return_value=None) as p:
            self.client.get(self._url("usa-nba:38"))
        p.return_value.get_team_logo_bytes.assert_not_called()

    # ---- aggregator fallback (unmirrored team) ---------------------------

    def test_fallback_serves_aggregator_bytes_on_local_miss(self):
        with self._patch_client(
            return_value=(b"AGGBYTES", "image/webp", '"agg-etag"')
        ):
            resp = self.client.get(self._url("nfl:KC"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(bytes(resp.content), b"AGGBYTES")
        self.assertEqual(resp["Content-Type"], "image/webp")
        self.assertEqual(resp["ETag"], '"agg-etag"')

    def test_fallback_304_when_if_none_match_matches_aggregator_etag(self):
        with self._patch_client(
            return_value=(b"AGGBYTES", "image/webp", '"agg-etag"')
        ):
            resp = self.client.get(
                self._url("nfl:KC"), HTTP_IF_NONE_MATCH='"agg-etag"'
            )
        self.assertEqual(resp.status_code, 304)
        self.assertEqual(resp["ETag"], '"agg-etag"')

    def test_404_when_neither_local_nor_aggregator_has_it(self):
        with self._patch_client(return_value=None):
            resp = self.client.get(self._url("usa-nba:999"))
        self.assertEqual(resp.status_code, 404)

    def test_rate_limited_returns_503_with_retry_after(self):
        with self._patch_client(
            side_effect=AggrigatorRateLimited("nfl:KC", 42)
        ):
            resp = self.client.get(self._url("nfl:KC"))
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp["Retry-After"], "42")

    def test_aggregator_error_returns_503(self):
        with self._patch_client(side_effect=AggrigatorError("boom")):
            resp = self.client.get(self._url("nfl:KC"))
        self.assertEqual(resp.status_code, 503)

    # ---- cache headers ----------------------------------------------------

    def test_error_responses_are_not_cached(self):
        with self._patch_client(side_effect=AggrigatorError("boom")):
            resp = self.client.get(self._url("nfl:KC"))
        self.assertIn("no-store", resp["Cache-Control"])
