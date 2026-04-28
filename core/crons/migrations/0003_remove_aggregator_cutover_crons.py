"""Remove periodic tasks that moved to the aggregator service.

The cutover (plan §7.1) shifted event ingestion, odds refresh, and settlement
out of MDProject. The corresponding task functions are gone from
``core.crons.tasks``, so leaving the periodic-task rows in the DB causes beat
to dispatch to non-existent tasks.

Forward: deletes the three dead PeriodicTask rows by name. Idempotent — a
filtered delete on a missing row is a no-op.

Reverse: no-op. The task functions no longer exist; there's nothing useful to
recreate.
"""
from django.db import migrations


DEAD_TASK_NAMES = [
    "event_cron",
    "settle_pending_cron",
    "warm_upcoming_odds_cron",
]


def remove_dead_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name__in=DEAD_TASK_NAMES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_crons", "0002_seed_warm_odds"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(remove_dead_tasks, reverse_code=migrations.RunPython.noop),
    ]
