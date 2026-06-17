"""get_team_logo_bytes returns (bytes, content_type, etag) or None on 404."""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    absolutize_logo_url,
)


class AbsolutizeLogoUrlTests(SimpleTestCase):
    @override_settings(AGG_PUBLIC_BASE="http://pub:9", AGGRIGATOR_BASE_URL="http://srv:8001")
    def test_relative_uses_public_base_first(self):
        self.assertEqual(
            absolutize_logo_url("/v1/teams/USL:1/logo"),
            "http://pub:9/v1/teams/USL:1/logo",
        )

    @override_settings(AGG_PUBLIC_BASE="", AGGRIGATOR_BASE_URL="http://localhost:8001")
    def test_relative_falls_back_to_server_base(self):
        self.assertEqual(
            absolutize_logo_url("/v1/teams/USL:1/logo"),
            "http://localhost:8001/v1/teams/USL:1/logo",
        )

    @override_settings(AGG_PUBLIC_BASE="http://pub:9", AGGRIGATOR_BASE_URL="http://srv:8001")
    def test_absolute_url_unchanged(self):
        url = "http://agg/v1/teams/USL:1/logo"
        self.assertEqual(absolutize_logo_url(url), url)

    def test_none_and_empty_pass_through(self):
        self.assertIsNone(absolutize_logo_url(None))
        self.assertEqual(absolutize_logo_url(""), "")


class GetTeamLogoBytesTests(SimpleTestCase):
    def _resp(self, status, content=b"", headers=None):
        m = mock.Mock()
        m.status_code = status
        m.content = content
        m.headers = headers or {}
        return m

    def test_returns_bytes(self):
        client = AggrigatorClient(base_url="http://agg")
        with mock.patch.object(
            client.session, "get",
            return_value=self._resp(
                200, b"PNGDATA", {"Content-Type": "image/png", "ETag": '"abc"'}
            ),
        ):
            result = client.get_team_logo_bytes("usa-nba:38")
        self.assertEqual(result, (b"PNGDATA", "image/png", '"abc"'))

    def test_404_returns_none(self):
        client = AggrigatorClient(base_url="http://agg")
        with mock.patch.object(
            client.session, "get", return_value=self._resp(404)
        ):
            self.assertIsNone(client.get_team_logo_bytes("usa-nba:999"))

    def test_429_raises_rate_limited_with_retry_after(self):
        from core.event.providers.aggregator_client import AggrigatorRateLimited

        client = AggrigatorClient(base_url="http://agg")
        with mock.patch.object(
            client.session, "get",
            return_value=self._resp(429, headers={"Retry-After": "42"}),
        ):
            with self.assertRaises(AggrigatorRateLimited) as cm:
                client.get_team_logo_bytes("usa-nba:38")
        self.assertEqual(cm.exception.retry_after, 42)

    def test_429_without_retry_after_defaults_to_60(self):
        from core.event.providers.aggregator_client import AggrigatorRateLimited

        client = AggrigatorClient(base_url="http://agg")
        with mock.patch.object(
            client.session, "get", return_value=self._resp(429)
        ):
            with self.assertRaises(AggrigatorRateLimited) as cm:
                client.get_team_logo_bytes("usa-nba:38")
        self.assertEqual(cm.exception.retry_after, 60)
