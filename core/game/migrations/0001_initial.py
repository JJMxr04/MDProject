# Hand-written initial migration for core_game.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core_event", "0001_initial"),
        ("core_match", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Bet",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True,
                        serialize=False, unique=True,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(default=timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner_decimal_odds_at_pick",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
                ),
                (
                    "player_2_decimal_odds_at_pick",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
                ),
                ("owner_picked_at", models.DateTimeField(blank=True, null=True)),
                ("player_2_picked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "owner_outcome",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core_event.selection",
                    ),
                ),
                (
                    "player_2_outcome",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core_event.selection",
                    ),
                ),
            ],
            options={
                "db_table": "core.bet",
            },
        ),
        migrations.CreateModel(
            name="Game",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                ("is_golden", models.BooleanField(default=False)),
                ("slot", models.SmallIntegerField(default=0)),
                (
                    "match",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="games",
                        to="core_match.match",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="owner_game",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "player_2",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="player_2_game",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="games",
                        to="core_event.event",
                    ),
                ),
                (
                    "bet",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game",
                        to="core_game.bet",
                    ),
                ),
            ],
            options={
                "db_table": "core.game",
            },
        ),
        migrations.AddConstraint(
            model_name="game",
            constraint=models.UniqueConstraint(
                fields=("match", "owner", "slot", "is_golden"),
                name="uq_game_match_owner_slot_golden",
            ),
        ),
    ]
