# Hand-written initial migration for the SportsGameOdds-backed event app.
#
# Replaces the prior SofaScore-era 0001/0002/0003 chain. Dev DB wipe is the
# rollout precondition (per api-switch/sports_game/refactor-plan.md §5).

import uuid

import core.event.models.team
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Sport",
            fields=[
                ("id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=64)),
                ("short_name", models.CharField(blank=True, max_length=48)),
                ("active", models.BooleanField(default=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "core_sport",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="League",
            fields=[
                ("id", models.CharField(max_length=48, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=128)),
                ("short_name", models.CharField(blank=True, max_length=48)),
                ("active", models.BooleanField(default=False)),
                ("refresh_cadence_minutes", models.PositiveIntegerField(default=720)),
                ("last_refreshed_at", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "sport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="leagues",
                        to="core_event.sport",
                    ),
                ),
            ],
            options={
                "db_table": "core_league",
                "ordering": ["sport_id", "name"],
            },
        ),
        migrations.AddIndex(
            model_name="league",
            index=models.Index(fields=["sport", "active"], name="core_league_sport_i_68cf7d_idx"),
        ),
        migrations.CreateModel(
            name="Team",
            fields=[
                ("id", models.CharField(max_length=80, primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                ("team_id", models.CharField(max_length=48)),
                ("name_long", models.CharField(max_length=128)),
                ("name_medium", models.CharField(blank=True, max_length=64)),
                ("name_short", models.CharField(blank=True, max_length=32)),
                ("primary_color", models.CharField(blank=True, max_length=9, null=True)),
                ("secondary_color", models.CharField(blank=True, max_length=9, null=True)),
                ("primary_contrast", models.CharField(blank=True, max_length=9, null=True)),
                ("secondary_contrast", models.CharField(blank=True, max_length=9, null=True)),
                ("stat_entity_id", models.CharField(blank=True, max_length=8)),
                (
                    "logo_url",
                    models.ImageField(
                        blank=True, null=True, upload_to=core.event.models.team.logo_upload_path
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "league",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teams",
                        to="core_event.league",
                    ),
                ),
                (
                    "sport",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teams",
                        to="core_event.sport",
                    ),
                ),
            ],
            options={
                "db_table": "core_team",
                "ordering": ["name_long"],
                "unique_together": {("league", "team_id")},
            },
        ),
        migrations.AddIndex(
            model_name="team",
            index=models.Index(fields=["league", "team_id"], name="core_team_league__b38412_idx"),
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                ("id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                (
                    "public_id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, unique=True
                    ),
                ),
                ("type", models.CharField(blank=True, max_length=16)),
                ("season_label", models.CharField(blank=True, max_length=64)),
                ("start_time", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("status_type", models.CharField(blank=True, db_index=True, max_length=32)),
                ("status_display", models.CharField(blank=True, max_length=64)),
                ("current_period_id", models.CharField(blank=True, max_length=16)),
                ("is_live", models.BooleanField(db_index=True, default=False)),
                ("is_finalized", models.BooleanField(default=False)),
                ("completed", models.BooleanField(default=False)),
                ("home_score", models.IntegerField(blank=True, null=True)),
                ("away_score", models.IntegerField(blank=True, null=True)),
                ("winner_code", models.SmallIntegerField(blank=True, null=True)),
                ("winner", models.CharField(blank=True, max_length=255, null=True)),
                ("feed_locked", models.BooleanField(default=False)),
                ("last_provider_refresh_at", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "sport",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="core_event.sport",
                    ),
                ),
                (
                    "league",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="core_event.league",
                    ),
                ),
                (
                    "home_team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="home_events",
                        to="core_event.team",
                    ),
                ),
                (
                    "away_team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="away_events",
                        to="core_event.team",
                    ),
                ),
            ],
            options={
                "db_table": "core_event_event",
                "ordering": ["-start_time"],
            },
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["league", "status_type", "start_time"],
                name="core_event__league__c5677f_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["sport", "status_type", "start_time"],
                name="core_event__sport_i_270637_idx",
            ),
        ),
        migrations.CreateModel(
            name="Market",
            fields=[
                ("id", models.CharField(max_length=128, primary_key=True, serialize=False)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("MONEYLINE", "Moneyline"),
                            ("SPREAD", "Spread"),
                            ("TOTAL", "Total"),
                            ("PROPS_GAME", "Props Game"),
                            ("PROPS_TEAM", "Props Team"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("type", models.CharField(db_index=True, max_length=64)),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("FULL_GAME", "Full Game"),
                            ("H1", "H1"), ("H2", "H2"),
                            ("Q1", "Q1"), ("Q2", "Q2"), ("Q3", "Q3"), ("Q4", "Q4"),
                            ("OVERTIME", "Overtime"),
                            ("PERIOD_N", "Period N"),
                            ("P1", "P1"), ("P2", "P2"), ("P3", "P3"),
                            ("SHOOTOUT", "Shootout"),
                            ("INNING_1", "Inning 1"), ("INNING_2", "Inning 2"),
                            ("INNING_3", "Inning 3"), ("INNING_4", "Inning 4"),
                            ("INNING_5", "Inning 5"), ("INNING_6", "Inning 6"),
                            ("INNING_7", "Inning 7"), ("INNING_8", "Inning 8"),
                            ("INNING_9", "Inning 9"),
                            ("INNINGS_1_5", "Innings 1 5"),
                            ("INNINGS_1_3", "Innings 1 3"),
                            ("MINUTES_5", "Minutes 5"),
                            ("MINUTES_10", "Minutes 10"),
                        ],
                        default="FULL_GAME",
                        max_length=16,
                    ),
                ),
                ("line", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("side", models.CharField(blank=True, max_length=8)),
                ("provider", models.CharField(default="sportsgameodds", max_length=32)),
                ("provider_market_id", models.CharField(blank=True, db_index=True, max_length=128)),
                ("provider_choice_group", models.CharField(blank=True, max_length=16)),
                ("is_live", models.BooleanField(default=False)),
                ("suspended", models.BooleanField(default=False)),
                ("last_updated", models.DateTimeField(db_index=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="markets",
                        to="core_event.event",
                    ),
                ),
                (
                    "sport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="core_event.sport"
                    ),
                ),
                (
                    "subject_team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core_event.team",
                    ),
                ),
            ],
            options={
                "db_table": "core_market",
            },
        ),
        migrations.AddIndex(
            model_name="market",
            index=models.Index(
                fields=["event", "category", "scope"], name="core_market_event_i_7f8981_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="market",
            index=models.Index(
                fields=["sport", "category", "is_live"], name="core_market_sport_i_c3d26a_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="market",
            index=models.Index(fields=["event", "type"], name="core_market_event_i_cc2b4a_idx"),
        ),
        migrations.CreateModel(
            name="Selection",
            fields=[
                ("id", models.CharField(max_length=160, primary_key=True, serialize=False)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("HOME", "Home"), ("AWAY", "Away"), ("DRAW", "Draw"),
                            ("OVER", "Over"), ("UNDER", "Under"),
                            ("YES", "Yes"), ("NO", "No"),
                            ("EVEN", "Even"), ("ODD", "Odd"),
                            ("1X", "Dc 1X"), ("X2", "Dc X2"), ("12", "Dc 12"),
                            ("NO_GOAL", "No Goal"),
                            ("CUSTOM", "Custom"),
                        ],
                        max_length=16,
                    ),
                ),
                ("label", models.CharField(max_length=128)),
                ("suspended", models.BooleanField(default=False)),
                (
                    "decimal_odds",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
                ),
                (
                    "opening_decimal_odds",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
                ),
                ("movement", models.SmallIntegerField(default=0)),
                (
                    "settlement_status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"), ("WON", "Won"), ("LOST", "Lost"),
                            ("PUSH", "Push"), ("VOID", "Void"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=8,
                    ),
                ),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "settlement_source",
                    models.CharField(
                        blank=True,
                        choices=[("PROVIDER", "Provider"), ("COMPUTED", "Computed"), ("MANUAL", "Manual")],
                        max_length=16,
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "market",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="selections",
                        to="core_event.market",
                    ),
                ),
            ],
            options={
                "db_table": "core_selection",
            },
        ),
        migrations.AddIndex(
            model_name="selection",
            index=models.Index(fields=["market", "type"], name="core_select_market__26e26c_idx"),
        ),
        migrations.AddIndex(
            model_name="selection",
            index=models.Index(
                fields=["settlement_status", "market"], name="core_select_settlem_994b7a_idx"
            ),
        ),
        migrations.CreateModel(
            name="OddsQuote",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("decimal_odds", models.DecimalField(decimal_places=4, max_digits=8)),
                ("captured_at", models.DateTimeField(db_index=True)),
                (
                    "selection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="quotes",
                        to="core_event.selection",
                    ),
                ),
            ],
            options={
                "db_table": "core_odds_quote",
            },
        ),
        migrations.AddIndex(
            model_name="oddsquote",
            index=models.Index(fields=["selection", "captured_at"], name="core_odds_q_selecti_37c0e5_idx"),
        ),
        migrations.AddConstraint(
            model_name="oddsquote",
            constraint=models.UniqueConstraint(
                fields=("selection", "captured_at"), name="uq_quote_selection_captured"
            ),
        ),
        migrations.CreateModel(
            name="Bookmaker",
            fields=[
                ("id", models.CharField(max_length=32, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=64)),
                ("active", models.BooleanField(default=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "core_bookmaker",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="BookmakerSelection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "decimal_odds",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=8, null=True),
                ),
                (
                    "spread",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
                ),
                (
                    "over_under",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
                ),
                ("available", models.BooleanField(default=True)),
                ("deeplink", models.URLField(blank=True, max_length=500)),
                ("last_updated_at", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "selection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="by_book",
                        to="core_event.selection",
                    ),
                ),
                (
                    "bookmaker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="quotes",
                        to="core_event.bookmaker",
                    ),
                ),
            ],
            options={
                "db_table": "core_bookmaker_selection",
                "unique_together": {("selection", "bookmaker")},
            },
        ),
        migrations.AddIndex(
            model_name="bookmakerselection",
            index=models.Index(
                fields=["selection", "available"], name="core_bookma_selecti_97c07c_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="bookmakerselection",
            index=models.Index(
                fields=["bookmaker", "available"], name="core_bookma_bookmak_2c534f_idx"
            ),
        ),
    ]
