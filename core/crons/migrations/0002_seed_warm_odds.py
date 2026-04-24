"""Seed the hybrid odds-warming periodic task.

Adds warm_upcoming_odds_cron to the scheduler. Idempotent.
"""
from django.db import migrations


CRON_NAME = "warm_upcoming_odds_cron"
CRON_TASK = "core.crons.tasks.warm_upcoming_odds_cron"
CRON_KWARGS = {
    "minute": "0",
    "hour": "*/6",       # every 6 hours
    "day_of_week": "*",
    "day_of_month": "*",
    "month_of_year": "*",
}


def seed(apps, schema_editor):
    CrontabSchedule = apps.get_model("django_celery_beat", "CrontabSchedule")
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    schedule, _ = CrontabSchedule.objects.get_or_create(**CRON_KWARGS)
    PeriodicTask.objects.get_or_create(
        name=CRON_NAME,
        defaults={"task": CRON_TASK, "crontab": schedule, "enabled": True},
    )


def unseed(apps, schema_editor):
    PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
    PeriodicTask.objects.filter(name=CRON_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_crons", "0001_seed_periodic_tasks"),
        ("django_celery_beat", "0019_alter_periodictasks_options"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
