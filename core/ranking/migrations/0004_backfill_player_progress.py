"""Backfill a PlayerProgress row for every existing user.

PlayerProgress was created lazily (on first ranked activity), so users who
signed up before earning anything had no row — the portal then showed no
level/XP for them. This get-or-creates a default row (level 1, 0 XP) for all
existing users; new users get one at signup via the post_save signal
(core/ranking/signals.py). Idempotent and reversible-as-noop.
"""

from django.db import migrations


def backfill_progress(apps, schema_editor):
    User = apps.get_model("core_user", "User")
    PlayerProgress = apps.get_model("core_ranking", "PlayerProgress")

    have = set(PlayerProgress.objects.values_list("user_id", flat=True))
    missing = User.objects.exclude(id__in=have).values_list("id", flat=True)
    PlayerProgress.objects.bulk_create(
        [PlayerProgress(user_id=uid) for uid in missing],
        batch_size=500,
    )


def noop(apps, schema_editor):
    # Reverse leaves the rows in place — dropping them would discard real
    # progress for anyone who has since earned XP.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core_ranking", "0003_xpevent_potd_pick"),
    ]

    operations = [
        migrations.RunPython(backfill_progress, noop),
    ]
