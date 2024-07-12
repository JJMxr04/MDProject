import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from core.tournament.models.tournament import Tournament, Round, TournamentManager, RoundManager
# from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
from core.user.models import User
from core.event.models.sport import Sport
from .tests import tournament_test_2
import logging
logger = logging.getLogger(__name__)
from core.tournament.unit_tests.tests.Support import Support
from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest
from core.tournament.unit_tests.tests.tourney_checks import TournamentChecks
import unittest
from core.tournament.models.tournament import Player
import logging
import math
import time
class TournamentCreationTestCase(TestCase):
    databases = ['default', 'test_mirror']
    # Level 6
    first_round_game_picks = {
        'data1': {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        },
        'data2': {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        },
        'data1_gg': {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        },
        'data2_gg': {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }
    }
    #  Level Five
    second_round_game_picks = {
        'data1': {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Philadelphia Eagles"
        },
        'data2': {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Buffalo Bills"
        },
        'data1_gg': {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Kansas City Chiefs"
        },
        'data2_gg': {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Las Vegas Raiders"
        }
    }
    # Level Four
    third_round_game_picks = {
        'data1': {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Miami Dolphins"
        },
        'data2': {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Baltimore Ravens"
        },
        'data1_gg': {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Los Angeles Chargers"
        },
        'data2_gg': {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Minnesota Vikings"
        }
    }
    # Level Three
    fourth_round_game_picks = {
        'data1': {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Dallas Cowboys"
        },
        'data2': {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Seattle Seahawks"
        },
        'data1_gg': {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Pittsburgh Steelers"
        },
        'data2_gg': {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Arizona Cardinals"
        }
    }
    # Level Two
    fifth_round_game_picks = {
        'data1': {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "New York Jets"
        },
        'data2': {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "Atlanta Falcons"
        },
        'data1_gg': {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "New Orleans Saints"
        },
        'data2_gg': {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "Detroit Lions"
        }
    }
    # Level One
    sixth_round_game_picks = {
        'data1': {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Tennessee Titans"
        },
        'data2': {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Indianapolis Colts"
        },
        'data1_gg': {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Washington Commanders"
        },
        'data2_gg': {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Miami Dolphins"
        }

    }
    # Level Zero
    seventh_round_game_picks = {
        'data1': {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Houston Texans"
        },
        'data2': {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Denver Broncos"
        },
        'data1_gg': {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "New England Patriots"
        },
        'data2_gg': {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "Los Angeles Chargers"
        }

    }

    # def test_tournament_2(self):
    #     expected_max_players = 2
    #     logger.info(f'Starting Tournament Simulation test with {expected_max_players} max and accepted players')
    #     Support().load_data_sport_team()
    #     expected_name = 'test2'
    #     expected_levels = math.log2(expected_max_players)
    #     test = tournament_test_2(max_players=expected_max_players, tourney_name=expected_name)
    #     time.sleep(30)
    #     tournament = Tournament.objects.get_object_by_id(id = test.tournament.id)
    #
    #     tournament_check = TournamentChecks(test_case=self,tournament=tournament,name=expected_name,max_players=expected_max_players)
    #     logger.info(f'Finished Tournament Simulation test with {expected_max_players} max and accepted players')

    def test_tournament_3(self):
        expected_max_players = 3
        logger.info(f'Starting Tournament Simulation test with {expected_max_players} max and accepted players')
        Support().load_data_sport_team()
        expected_name = 'test4'
        expected_levels = math.log2(expected_max_players)
        test = tournament_test_2(max_players=expected_max_players, tourney_name=expected_name)
        time.sleep(30)
        tournament = Tournament.objects.get_object_by_id(id = test.tournament.id)

        tournament_check = TournamentChecks(test_case=self,tournament=tournament,name=expected_name,max_players=expected_max_players)
        logger.info(f'Finished Tournament Simulation test with {expected_max_players} max and accepted players')

    # def test_tournament_4(self):
    #     expected_max_players = 4
    #     logger.info(f'Starting Tournament Simulation test with {expected_max_players} max and accepted players')
    #     Support().load_data_sport_team()
    #     expected_name = 'test4'
    #     expected_levels = math.log2(expected_max_players)
    #     test = tournament_test_2(max_players=expected_max_players, tourney_name=expected_name)
    #     time.sleep(30)
    #     tournament = Tournament.objects.get_object_by_id(id = test.tournament.id)
    #
    #     tournament_check = TournamentChecks(test_case=self,tournament=tournament,name=expected_name,max_players=expected_max_players)
    #     logger.info(f'Finished Tournament Simulation test with {expected_max_players} max and accepted players')
