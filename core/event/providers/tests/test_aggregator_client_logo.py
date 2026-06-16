"""get_team_logo_bytes returns (bytes, content_type, etag) or None on 404."""

from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from core.event.providers.aggregator_client import AggrigatorClient


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
