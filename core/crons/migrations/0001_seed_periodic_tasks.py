"""Seed default periodic tasks.

These mirror the defaults in settings.CELERY_BEAT_SCHEDULE so the DB-backed
scheduler (django_celery_beat) starts with sensible entries out of the box.
Staff can then edit them from /admin/django_celery_beat/periodictask/
without touching settings.

Idempotent: uses get_or_create by task name, so re-running this migration or
applying it to an environment where an admin already added a matching task
won't double-create anything.
"""
from django.db import migrations


# (periodic-task name, celery-task dotted path, crontab kwargs, enabled?)
DEFAULT_PERIODIC_TASKS = [
    (
        "event_cron",
        "core.crons.tasks.event_cron",
        {"minute": "0", "hour": "*/12", "day_of_week": "*",
         "day_of_month": "*", "month_of_year": "*"},
        True,
    ),
    (
        "settle_pending_cron",
        "core.crons.tasks.settle_pending_cron",
        {"minute": "30", "hour": "3", "day_of_week": "*",
         "day_of_month": "*", "month_of_year": "*"},
        True,
    ),
    (
        "print_cron_jobs",
        "core.crons.tasks.print_cron_jobs",
        {"minute": "*/5", "hour": "*", "day_of_week": "*",
         "day_of_month": "*", "month_of_year": "*"},
        True,
    ),
]


def seed_periodic_tasks(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")

    for name, task_path, cron_kwargs, enabled in DEFAULT_PERIODIC_TASKS:
        schedule, _ = CrontabSchedule.objects.get_or_create(**cron_kwargs)
        PeriodicTask.objects.get_or_create(
            name=name,
            defaults={
                "task": task_path,
                "crontab": schedule,
                "enabled": enabled,
            },
        )


def unseed_periodic_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(
        name__in=[name for name, *_ in DEFAULT_PERIODIC_TASKS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        # django_celery_beat must have its own tables in place.
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed_periodic_tasks, reverse_code=unseed_periodic_tasks),
    ]
