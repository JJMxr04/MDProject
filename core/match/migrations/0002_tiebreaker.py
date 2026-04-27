# Adds TieBreaker (FK to core_game.Game) and the Match.tiebreaker FK.
# Split out so core_game.0001_initial can depend on core_match.0001_initial
# without a circular reference.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_match", "0001_initial"),
        ("core_game", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TieBreaker",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("total", models.IntegerField(default=0)),
                ("owner_total", models.IntegerField(default=0)),
                ("player_2_total", models.IntegerField(default=0)),
                (
                    "winner",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="winner_tiebreaker",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "golden_game",
                    models.ForeignKey(
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tiebreaker_golden_game",
                        to="core_game.game",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="match",
            name="tiebreaker",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="match_tiebreaker",
                to="core_match.tiebreaker",
            ),
        ),
    ]
