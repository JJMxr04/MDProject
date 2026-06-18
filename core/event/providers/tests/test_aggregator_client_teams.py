"""The event AggrigatorClient authenticates all calls + exposes list_teams."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.event.providers.aggregator_client import AggrigatorClient


class TenantKeyHeaderTests(SimpleTestCase):
    @override_settings(AGGRIGATOR_SERVICE_KEY="agg_live_topsecretkey")
    @patch.dict("os.environ", {"AGGRIGATOR_SERVICE_KEY": ""})
    def test_key_set_attaches_header_to_session(self):
        client = AggrigatorClient()
        self.assertEqual(
            client.session.headers.get("X-Aggrigator-Tenant-Key"),
            "agg_live_topsecretkey",
        )

    @override_settings(AGGRIGATOR_SERVICE_KEY="")
    @patch.dict("os.environ", {"AGGRIGATOR_SERVICE_KEY": ""})
    def test_no_key_means_no_header(self):
        client = AggrigatorClient()
        self.assertNotIn("X-Aggrigator-Tenant-Key", client.session.headers)


class ListTeamsTests(SimpleTestCase):
    def test_list_teams_builds_params_and_delegates_to_get(self):
        client = AggrigatorClient()
        with patch.object(client, "_get", return_value={"items": [], "pages": 1}) as mget:
            out = client.list_teams(page=2, page_size=50, league_id="NFL")
        mget.assert_called_once_with(
            "/v1/teams", params={"page": 2, "page_size": 50, "league_id": "NFL"}
        )
        self.assertEqual(out, {"items": [], "pages": 1})

    def test_list_teams_omits_none_league_id(self):
        client = AggrigatorClient()
        with patch.object(client, "_get", return_value={}) as mget:
            client.list_teams()
        mget.assert_called_once_with("/v1/teams", params={"page": 1, "page_size": 200})

    def test_list_teams_none_body_coerced_to_empty_dict(self):
        client = AggrigatorClient()
        with patch.object(client, "_get", return_value=None):
            self.assertEqual(client.list_teams(), {})
