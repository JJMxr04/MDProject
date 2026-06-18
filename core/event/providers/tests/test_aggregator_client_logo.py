"""get_team_logo_bytes returns (bytes, content_type, etag) or None on 404."""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from core.event.providers.aggregator_client import (
    AggrigatorClient,
    proxy_logo_url,
)


class ProxyLogoUrlTests(SimpleTestCase):
    """An aggregator team-logo URL is rewritten to MDProject's same-origin
    proxy endpoint, so the browser never calls the (key-gated) aggregator."""

    def test_relative_url_rewritten_to_proxy(self):
        self.assertEqual(
            proxy_logo_url("/v1/teams/USL:1/logo"),
            reverse("team-logo", kwargs={"team_id": "USL:1"}),
        )

    def test_absolute_aggregator_url_rewritten_to_proxy(self):
        self.assertEqual(
            proxy_logo_url("http://agg:8001/v1/teams/USL:1/logo"),
            reverse("team-logo", kwargs={"team_id": "USL:1"}),
        )

    def test_team_id_with_colon_preserved(self):
        self.assertEqual(
            proxy_logo_url("/v1/teams/usa-nba:38/logo"),
            reverse("team-logo", kwargs={"team_id": "usa-nba:38"}),
        )

    def test_non_logo_url_unchanged(self):
        url = "https://cdn.example.com/some/other/image.png"
        self.assertEqual(proxy_logo_url(url), url)

    def test_none_and_empty_pass_through(self):
        self.assertIsNone(proxy_logo_url(None))
        self.assertEqual(proxy_logo_url(""), "")


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
