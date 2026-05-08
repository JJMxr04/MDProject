"""Remove the ``print_cron_jobs`` periodic task.

Migration 0001 seeded a 5-minute heartbeat task that printed a single
log line so an operator could eyeball whether beat was alive. The
``/admin/status/`` page now answers the same question via
``celery.app.control.Inspect.ping()`` — no extra task firing every
5 min, no rows in ``django_celery_results`` for an action with no
useful side effect.

The ``@shared_task`` definition has also been removed from
``core.crons.tasks``, so leaving the PeriodicTask row in place would
cause beat to dispatch to a non-existent task.

Forward: deletes the row by name. Idempotent — a filtered delete on
a missing row is a no-op.

Reverse: no-op. The task function no longer exists.
"""
from django.db import migrations


DEAD_TASK_NAME = "print_cron_jobs"


def remove_print_cron_jobs(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=DEAD_TASK_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_crons", "0003_remove_aggregator_cutover_crons"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(remove_print_cron_jobs, reverse_code=migrations.RunPython.noop),
    ]
