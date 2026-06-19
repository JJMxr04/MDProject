from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from core.admin import status

User = get_user_model()


class BackfillLogosViewTests(TestCase):
    def setUp(self):
        self.url = reverse("core-admin:admin_backfill_logos")
        self.staff = User.objects.create_user(
            username="staff", email="staff@example.com", password="pw-123456789",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

    def test_get_is_rejected_post_only(self):
        self.client.force_login(self.staff)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    def test_logged_in_non_staff_is_blocked(self):
        non_staff = User.objects.create_user(
            username="member", email="member@example.com", password="pw-123456789",
        )
        # default is_staff=False
        self.client.force_login(non_staff)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    @patch("core.admin.views.run_backfill_team_logos", return_value=7)
    def test_staff_post_enqueues_and_flashes_count(self, mock_backfill):
        self.client.force_login(self.staff)
        resp = self.client.post(self.url, follow=True)
        mock_backfill.assert_called_once_with()
        self.assertEqual(resp.redirect_chain[-1][0], reverse("core-admin:admin_status"))
        self.assertIn("queued 7 team-logo", resp.content.decode())


class SyncTeamDataViewTests(TestCase):
    def setUp(self):
        self.url = reverse("core-admin:admin_sync_team_data")
        self.staff = User.objects.create_user(
            username="staff2", email="staff2@example.com", password="pw-123456789",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

    def test_get_is_rejected_post_only(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_anonymous_redirected_to_login(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    def test_logged_in_non_staff_is_blocked(self):
        non_staff = User.objects.create_user(
            username="member2", email="member2@example.com", password="pw-123456789",
        )
        self.client.force_login(non_staff)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("admin_status", resp["Location"])

    @patch("core.admin.views.sync_team_data_task")
    def test_staff_post_defers_task_and_redirects(self, mock_task):
        self.client.force_login(self.staff)
        resp = self.client.post(self.url, follow=True)
        mock_task.defer.assert_called_once_with()
        self.assertEqual(resp.redirect_chain[-1][0], reverse("core-admin:admin_status"))
        self.assertIn("Team-data sync queued", resp.content.decode())


class ProcrastinateStatusQueryTests(TestCase):
    """Exercise the /admin/status/ helpers against the real Procrastinate 3.x
    schema (created by procrastinate.contrib.django migrations in the test DB).

    Regression guard for the celery-era columns that didn't survive the cutover:
    ``procrastinate_jobs.attempted_at`` and ``.periodic_id`` don't exist in 3.x,
    so the old queries raised, got swallowed, and every cron rendered "never / 0"
    while the worker tile read "unknown". Requires Postgres — the queries use
    enums, ``FILTER`` and ``INTERVAL`` (the project's default + test DB).
    """

    def _insert_finished_job(self, task_name, status_value="succeeded"):
        """Insert a job and drive it todo -> doing -> <status_value> so the
        Procrastinate status triggers write the matching events (with at=NOW())
        exactly as a real worker would."""
        with connection.cursor() as cur:
            cur.execute(
                "INSERT INTO procrastinate_jobs (queue_name, task_name, status) "
                "VALUES ('default', %s, 'todo') RETURNING id",
                [task_name],
            )
            job_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE procrastinate_jobs SET status='doing' WHERE id=%s", [job_id]
            )
            cur.execute(
                "UPDATE procrastinate_jobs SET status=%s::procrastinate_job_status "
                "WHERE id=%s",
                [status_value, job_id],
            )
        return job_id

    def _insert_worker(self, heartbeat_sql="NOW()"):
        with connection.cursor() as cur:
            cur.execute(
                f"INSERT INTO procrastinate_workers (last_heartbeat) "
                f"VALUES ({heartbeat_sql})"
            )

    def test_beat_schedule_counts_runs_and_last_run(self):
        self._insert_finished_job("core.potd.curate_pick_of_day")
        by_name = {r["name"]: r for r in status.get_beat_schedule()}
        # The periodic task must be discovered from the registry...
        self.assertIn("core.potd.curate_pick_of_day", by_name)
        potd = by_name["core.potd.curate_pick_of_day"]
        # ...and carry stats from the job we just ran (was 0 / None before).
        self.assertGreaterEqual(potd["total_runs"], 1)
        self.assertIsNotNone(potd["last_run_at"])

    def test_recent_results_includes_succeeded_job(self):
        self._insert_finished_job("core.potd.sync_results")
        results = status.get_recent_results(limit=10)
        self.assertTrue(
            any(
                r["task_name"] == "core.potd.sync_results"
                and r["status"] == "SUCCEEDED"
                and r["date_done"] is not None
                for r in results
            ),
            results,
        )

    def test_worker_status_ok_with_recent_heartbeat(self):
        self._insert_worker()
        item = status.get_worker_status()
        self.assertEqual(item.state, status.State.OK)
        self.assertGreaterEqual(item.extra["live_workers"], 1)

    def test_worker_status_down_when_heartbeat_stale(self):
        self._insert_worker("NOW() - INTERVAL '1 hour'")
        item = status.get_worker_status()
        self.assertEqual(item.state, status.State.DOWN)

    def test_worker_status_unknown_when_no_worker_or_jobs(self):
        item = status.get_worker_status()
        self.assertEqual(item.state, status.State.UNKNOWN)
