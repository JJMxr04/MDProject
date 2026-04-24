"""Drop the rigid 5+5+1 game FK columns and the cached score/completion
fields from Match. Per api-switch/game-match-audit-plan.md §4.3, scores
are now derived from Selection.settlement_status (see core/match/scoring.py)
and the games come from Game.match reverse relation."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core_match", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(model_name="match", name="player_1_game_1"),
        migrations.RemoveField(model_name="match", name="player_1_game_2"),
        migrations.RemoveField(model_name="match", name="player_1_game_3"),
        migrations.RemoveField(model_name="match", name="player_1_game_4"),
        migrations.RemoveField(model_name="match", name="player_1_game_5"),
        migrations.RemoveField(model_name="match", name="player_2_game_1"),
        migrations.RemoveField(model_name="match", name="player_2_game_2"),
        migrations.RemoveField(model_name="match", name="player_2_game_3"),
        migrations.RemoveField(model_name="match", name="player_2_game_4"),
        migrations.RemoveField(model_name="match", name="player_2_game_5"),
        migrations.RemoveField(model_name="match", name="golden_game"),

        migrations.RemoveField(model_name="match", name="player_1_game_1_completed"),
        migrations.RemoveField(model_name="match", name="player_1_game_2_completed"),
        migrations.RemoveField(model_name="match", name="player_1_game_3_completed"),
        migrations.RemoveField(model_name="match", name="player_1_game_4_completed"),
        migrations.RemoveField(model_name="match", name="player_1_game_5_completed"),
        migrations.RemoveField(model_name="match", name="player_2_game_1_completed"),
        migrations.RemoveField(model_name="match", name="player_2_game_2_completed"),
        migrations.RemoveField(model_name="match", name="player_2_game_3_completed"),
        migrations.RemoveField(model_name="match", name="player_2_game_4_completed"),
        migrations.RemoveField(model_name="match", name="player_2_game_5_completed"),
        migrations.RemoveField(model_name="match", name="golden_game_completed"),

        migrations.RemoveField(model_name="match", name="player_1_score"),
        migrations.RemoveField(model_name="match", name="player_2_score"),

        migrations.AlterModelOptions(
            name="match",
            options={},
        ),
        migrations.AlterModelTable(
            name="match",
            table="core.match",
        ),
    ]
