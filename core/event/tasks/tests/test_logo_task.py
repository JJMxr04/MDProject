"""fetch_team_logo get-or-create against a mocked aggregator client."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from core.event.models import League, Sport, Team, TeamLogo
from core.event.tasks import logos


class FetchTeamLogoTests(TestCase):
    def setUp(self):
        sport = Sport.objects.create(id="basketball", name="Basketball")
        league = League.objects.create(id="usa-nba", sport=sport, name="NBA")
        Team.objects.create(
            id="usa-nba:38", league=league, team_id="38", sport=sport,
            name_long="Lakers",
        )

    def test_stores_bytes(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes",
            return_value=(b"PNGDATA", "image/png", '"abc"'),
        ):
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "ok")
        row = TeamLogo.objects.get(pk="usa-nba:38")
        self.assertEqual(bytes(row.image), b"PNGDATA")
        self.assertEqual(row.etag, "abc")

    def test_negative_caches_404(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes", return_value=None
        ):
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "missing")
        self.assertEqual(TeamLogo.objects.get(pk="usa-nba:38").status, "missing")

    def test_idempotent_ok(self):
        TeamLogo.objects.create(
            team_id="usa-nba:38", image=b"X", content_type="image/png",
            byte_size=1, etag="e", status="ok",
        )
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes"
        ) as fetch:
            status = logos.fetch_team_logo("usa-nba:38")
        self.assertEqual(status, "ok")
        fetch.assert_not_called()

    def test_team_not_found(self):
        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes"
        ) as fetch:
            status = logos.fetch_team_logo("usa-nba:999")
        self.assertEqual(status, "team_not_found")
        fetch.assert_not_called()

    def test_429_does_not_write_missing_row(self):
        # A rate-limit must NOT be cached as a 30-day 'missing' — the logo
        # isn't absent, we were just throttled. The exception propagates so
        # the task retries; no TeamLogo row is created.
        from core.event.providers.aggregator_client import AggrigatorRateLimited

        with mock.patch.object(
            logos.AggrigatorClient, "get_team_logo_bytes",
            side_effect=AggrigatorRateLimited("usa-nba:38", 30),
        ):
            with self.assertRaises(AggrigatorRateLimited):
                logos.fetch_team_logo("usa-nba:38")
        self.assertFalse(TeamLogo.objects.filter(pk="usa-nba:38").exists())


class LogoRetryStrategyTests(TestCase):
    def _job(self, attempts):
        return mock.Mock(attempts=attempts)

    def test_429_retry_honors_server_retry_after(self):
        from datetime import datetime, timezone

        from core.event.providers.aggregator_client import AggrigatorRateLimited

        strat = logos._LogoRetry(max_attempts=3, linear_wait=60)
        before = datetime.now(timezone.utc)
        decision = strat.get_retry_decision(
            exception=AggrigatorRateLimited("t", 17), job=self._job(0)
        )
        # RetryDecision(retry_in=...) materializes as retry_at = now + delta.
        delta = (decision.retry_at - before).total_seconds()
        self.assertGreaterEqual(delta, 17)
        self.assertLess(delta, 20)

    def test_non_429_falls_back_to_linear(self):
        from datetime import datetime, timezone

        strat = logos._LogoRetry(max_attempts=3, linear_wait=60)
        before = datetime.now(timezone.utc)
        decision = strat.get_retry_decision(
            exception=ValueError("boom"), job=self._job(1)
        )
        # linear: wait(0) + linear_wait*attempts(60*1) = 60s
        delta = (decision.retry_at - before).total_seconds()
        self.assertGreaterEqual(delta, 60)
        self.assertLess(delta, 63)

    def test_caps_at_max_attempts(self):
        from core.event.providers.aggregator_client import AggrigatorRateLimited

        strat = logos._LogoRetry(max_attempts=3, linear_wait=60)
        decision = strat.get_retry_decision(
            exception=AggrigatorRateLimited("t", 5), job=self._job(3)
        )
        self.assertIsNone(decision)
