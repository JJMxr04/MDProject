"""Game/Bet refactor — see api-switch/game-match-audit-plan.md §4.

- Drop snapshot fields on Game (commence_time, deadline_time, completed,
  home_team, away_team, winner, owner_choice, player_2_choice, match_id).
- Add real Game.match FK + is_golden + slot.
- Drop Bet's denormalized settlement booleans + market FK.
- Add Bet snapshot odds and picked_at timestamps.
- Re-shape Bet selection FKs to PROTECT with related_name='+'.
- Convert Game.bet to OneToOne.

Dev DB wipe is acceptable per refactor-plan.md §5; explicit non-null
defaults below assume empty tables (Game/Match aren't holding production
rows on v2 yet).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_game", "0001_initial"),
        ("core_match", "0002_drop_game_fks_and_score_caches"),
        ("core_event", "0002_alter_market_scope"),
    ]

    operations = [
        # --- Bet: drop legacy settlement cache + market field
        migrations.RemoveField(model_name="bet", name="market"),
        migrations.RemoveField(model_name="bet", name="owner_outcome_correct"),
        migrations.RemoveField(model_name="bet", name="player_2_outcome_correct"),
        migrations.RemoveField(model_name="bet", name="is_owner_outcome_processed"),
        migrations.RemoveField(model_name="bet", name="is_player_2_outcome_processed"),
        migrations.RemoveField(model_name="bet", name="is_processed"),

        # --- Bet: re-shape selection FKs (PROTECT + '+' related_name)
        migrations.AlterField(
            model_name="bet",
            name="owner_outcome",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core_event.selection",
            ),
        ),
        migrations.AlterField(
            model_name="bet",
            name="player_2_outcome",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core_event.selection",
            ),
        ),

        # --- Bet: snapshot odds + picked_at
        migrations.AddField(
            model_name="bet",
            name="owner_decimal_odds_at_pick",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=8, null=True
            ),
        ),
        migrations.AddField(
            model_name="bet",
            name="player_2_decimal_odds_at_pick",
            field=models.DecimalField(
                blank=True, decimal_places=4, max_digits=8, null=True
            ),
        ),
        migrations.AddField(
            model_name="bet",
            name="owner_picked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bet",
            name="player_2_picked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),

        # --- Game: drop snapshot fields and the dead string match_id
        migrations.RemoveField(model_name="game", name="commence_time"),
        migrations.RemoveField(model_name="game", name="deadline_time"),
        migrations.RemoveField(model_name="game", name="completed"),
        migrations.RemoveField(model_name="game", name="home_team"),
        migrations.RemoveField(model_name="game", name="away_team"),
        migrations.RemoveField(model_name="game", name="winner"),
        migrations.RemoveField(model_name="game", name="owner_choice"),
        migrations.RemoveField(model_name="game", name="player_2_choice"),
        migrations.RemoveField(model_name="game", name="match_id"),

        # --- Game: real Match FK + is_golden + slot.
        # Non-null on the assumption the games table is empty (dev wipe per
        # refactor-plan §5). Production never ran v2 picks long enough to hold
        # rows.
        migrations.AddField(
            model_name="game",
            name="match",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="games",
                to="core_match.match",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="game",
            name="is_golden",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="game",
            name="slot",
            field=models.SmallIntegerField(default=0),
        ),

        # --- Game.event: now PROTECT (events are append-only; never delete a
        #     row that has live games on it)
        migrations.AlterField(
            model_name="game",
            name="event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="games",
                to="core_event.event",
            ),
        ),

        # --- Game.bet: now OneToOne so reverse access is `bet.game`
        migrations.AlterField(
            model_name="game",
            name="bet",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="game",
                to="core_game.bet",
            ),
        ),

        # --- Uniqueness: one slot per (match, owner) combination
        migrations.AddConstraint(
            model_name="game",
            constraint=models.UniqueConstraint(
                fields=["match", "owner", "slot", "is_golden"],
                name="uq_game_match_owner_slot_golden",
            ),
        ),
    ]
