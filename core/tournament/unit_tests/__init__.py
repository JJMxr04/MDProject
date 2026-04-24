# Quarantined.
#
# The whole `core.tournament.unit_tests` package depends on the pre-SofaScore
# odds API: TeamScoreSerializer, SportCron, TeamCron, Sport.objects.get_by_key,
# Event.objects.get_event_state, the Match.player_*_game_N FK shape, and
# Game.objects.update_by_id. Every one of those was deleted across the
# api-switch refactors (refactor-plan.md, odds-system-plan.md,
# game-match-audit-plan.md) and there are no live callers — see the fully
# commented-out core/tournament/tests.py.
#
# Re-enable the imports below only after rewriting Support.py + the
# Tourney_Simulator_*.py files against the new APIs (or delete the package).
#
# from .unit_test_all import TournamentCreationTestCase
# from .unit_test_missing_more_then_2_players import TournamentCreationMissingPlayersTestCase
