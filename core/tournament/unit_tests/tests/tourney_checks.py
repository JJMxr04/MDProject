import json

# from .tests import tournament_test_1
import logging
import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from core.event.models.sport import Sport
from core.tournament.models.tournament import Round, RoundManager, Tournament, TournamentManager

# from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
from core.user.models import User

logger = logging.getLogger(__name__)
import logging
import math
import time
import unittest
from uuid import UUID

from core.event.models.event import Event
from core.match.serializers.match import MatchSerializer
from core.tournament.models.tournament import Player
from core.tournament.serializers.tournament import RoundSerializer, TournamentSerializer
from core.tournament.unit_tests.tests.Support import Support
from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super(UUIDEncoder, self).default(obj)
class TournamentChecks(TestCase):
    first_round_data = {
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

    second_round_data = {
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

    third_round_data = {
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

    fourth_round_data = {
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

    fifth_round_data = {
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

    sixth_round_data = {
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

    seventh_round_data = {
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

    # All the checks

    def __init__(self,test_case, tournament,name, max_players):
        self.test_case = test_case
        self.tournamentCheck(tournament=tournament,name=name,max_players=max_players)



    def eventCheck(self):
        pass
    def gameCheck(self,owner_data,player_2_data,match,game,owner,player_2):
        expected_owner = owner
        actual_owner = game.owner
        self.test_case.assertEqual(expected_owner, actual_owner, f"Game owner mismatch: Expected {expected_owner}, but got {actual_owner}")

        expected_player_2 = player_2
        actual_player_2 = game.player_2
        self.test_case.assertEqual(expected_player_2, actual_player_2, f"Game Player 2 mismatch: Expected {expected_player_2}, but got {actual_player_2}")

        expected_event = Event.objects.get_object_by_id(owner_data["event_id"])
        actual_event = game.event
        self.test_case.assertEqual(expected_event, actual_event,f"Game Owner Event mismatch: Expected {expected_event}, but got {actual_event}")

        expected_owner_choice = owner_data["player_choice"]
        actual_owner_choice = game.owner_choice
        self.test_case.assertEqual(expected_owner_choice, actual_owner_choice, f"Game Owner Choice mismatch: Expected {expected_owner_choice}, but got {actual_owner_choice}")

        expected_player_2_event = Event.objects.get_object_by_id(player_2_data["event_id"])
        actual_player_2_event = game.event
        self.test_case.assertEqual(expected_player_2_event, actual_player_2_event,
                                   f"Game Player 2 Event mismatch: Expected {expected_player_2_event}, but got {actual_player_2_event}")

        expected_player_2_choice = player_2_data["player_choice"]
        actual_player_2_choice = game.player_2_choice
        self.test_case.assertEqual(expected_player_2_choice, actual_player_2_choice,
                                   f"Game Player 2 Choice mismatch: Expected {expected_player_2_choice}, but got {actual_player_2_choice}")

        expected_owner_choice = owner_data["player_choice"]
        actual_owner_choice = game.owner_choice
        self.test_case.assertEqual(expected_owner_choice, actual_owner_choice,
                                   f"Game Owner Choice mismatch: Expected {expected_owner_choice}, but got {actual_owner_choice}")



    # def goldenGameCheck(self, owner_data, player_2_data, match, game, owner, player_2):
    #
    #     expected_owner = owner
    #     actual_owner = game.owner
    #     self.test_case.assertEqual(expected_owner, actual_owner,
    #                                f"Game owner mismatch: Expected {expected_owner}, but got {actual_owner}")
    #
    #     expected_player_2 = player_2
    #     actual_player_2 = game.player_2
    #     self.test_case.assertEqual(expected_player_2, actual_player_2,
    #                                f"Game Player 2 mismatch: Expected {expected_player_2}, but got {actual_player_2}")
    #
    #     expected_event = owner_data["event_id"]
    #     actual_event = game.event
    #     self.test_case.assertEqual(expected_event, actual_event,
    #                                f"Game Owner Event mismatch: Expected {expected_event}, but got {actual_event}")
    #
    #     expected_owner_choice = owner_data["player_choice"]
    #     actual_owner_choice = game.owner_choice
    #     self.test_case.assertEqual(expected_owner_choice, actual_owner_choice,
    #                                f"Game Owner Choice mismatch: Expected {expected_owner_choice}, but got {actual_owner_choice}")
    #
    #     expected_player_2_event = player_2_data["event_id"]
    #     actual_player_2_event = game.event
    #     self.test_case.assertEqual(expected_player_2_event, actual_player_2_event,
    #                                f"Game Player 2 Event mismatch: Expected {expected_player_2_event}, but got {actual_player_2_event}")
    #
    #     expected_player_2_choice = player_2_data["player_choice"]
    #     actual_player_2_choice = game.player_2_choice
    #     self.test_case.assertEqual(expected_player_2_choice, actual_player_2_choice,
    #                                f"Game Player 2 Choice mismatch: Expected {expected_player_2_choice}, but got {actual_player_2_choice}")
    #
    #     expected_owner_choice = owner_data["player_choice"]
    #     actual_owner_choice = game.owner_choice
    #     self.test_case.assertEqual(expected_owner_choice, actual_owner_choice,
    #                                f"Game Owner Choice mismatch: Expected {expected_owner_choice}, but got {actual_owner_choice}")


    def matchChecks(self,round,match,tournament_levels):
        expected_match_winner = match.player_1
        expected_round_winner = round.player_1
        actual_match_winner = match.winner
        actual_round_winner = round.winner
        expected_round_winner_user = match.player_1
        actual_round_winner_user = round.winner.player



        self.test_case.assertEqual(expected_match_winner, actual_match_winner, f"Match Winner mismatch: Expected {expected_match_winner}, but got {actual_match_winner}")
        self.test_case.assertEqual(expected_round_winner, actual_round_winner, f"Round Winner mismatch: Expected {expected_round_winner}, but got {actual_round_winner}")
        self.test_case.assertEqual(expected_round_winner_user, actual_round_winner_user, f"Round-Match-User winner mismatch: Expected {expected_round_winner_user}, but got {actual_round_winner_user}")

        expected_match_state = 'completed'
        actual_match_state = match.match_state
        self.test_case.assertEqual(expected_match_state, actual_match_state, f"Match State mismatch: Expected {expected_match_state}, but got {actual_match_state}")

        expected_player_1_score = 12
        actual_player_1_score =match.player_1_score

        self.test_case.assertEqual(expected_player_1_score, actual_player_1_score, f"Match Player 1 Score mismatch: Expected {expected_player_1_score}, but got {actual_player_1_score}")

        expected_player_2_score = 0
        actual_player_2_score = match.player_2_score

        self.test_case.assertEqual(expected_player_2_score, actual_player_2_score,
                                   f"Match Player 2 Score mismatch: Expected {expected_player_2_score}, but got {actual_player_2_score}")


        #Game Checks

        levels = tournament_levels-1
        round_level =round.level_num


        if levels - round_level == 0:
            data = self.first_round_data
        if levels - round_level == 1:
            data = self.second_round_data
        if levels - round_level == 2:
            data = self.third_round_data
        if levels - round_level == 3:
            data = self.forth_round_data
        if levels - round_level == 4:
            data = self.firth_round_data
        if levels - round_level == 5:
            data = self.sixth_round_data
        if levels - round_level == 6:
            data = self.seventh_round_data


        self.gameCheck(data['data1'], data['data2'], match, match.player_1_game_1, match.player_1, match.player_2)
        self.gameCheck(data['data1'], data['data2'], match, match.player_1_game_2, match.player_1, match.player_2)
        self.gameCheck(data['data1'], data['data2'], match, match.player_1_game_3, match.player_1, match.player_2)
        self.gameCheck(data['data1'], data['data2'], match, match.player_1_game_4, match.player_1, match.player_2)
        self.gameCheck(data['data1'], data['data2'], match, match.player_1_game_5, match.player_1, match.player_2)

        self.gameCheck(data['data2'], data['data1'], match, match.player_2_game_1, match.player_2, match.player_1)
        self.gameCheck(data['data2'], data['data1'], match, match.player_2_game_2, match.player_2, match.player_1)
        self.gameCheck(data['data2'], data['data1'], match, match.player_2_game_3, match.player_2, match.player_1)
        self.gameCheck(data['data2'], data['data1'], match, match.player_2_game_4, match.player_2, match.player_1)
        self.gameCheck(data['data2'], data['data1'], match, match.player_2_game_5, match.player_2, match.player_1)

        self.gameCheck(data['data1_gg'], data['data2_gg'], match, match.golden_game, match.player_1, match.player_2)










    def roundCheck(self,round):
        pass

    def roundRecusion(self,round,level,tournament):


        # recusion dfs
        if not round:
            return
        self.roundRecusion(round.prev_round_1,level +1,tournament=tournament)
        self.roundRecusion(round.prev_round_2,level+1,tournament=tournament)
        print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        print(f'Round Recursion {round}')
        print(json.dumps(RoundSerializer(round).data,indent=4, cls=UUIDEncoder))
        # print(f'Round Recursion - Match {round}')
        # print(json.dumps(MatchSerializer(round.match).data, indent=4, cls=UUIDEncoder))
        print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')

        expected_level = level
        actual_level = round.level_num
        expected_tournament = tournament
        actual_tournament = round.tournament
        self.test_case.assertEqual(expected_level, actual_level,
                                   f"Round Level mismatch: Expected {expected_level}, but got {actual_level}")
        self.test_case.assertEqual(expected_level, actual_level,
                                   f"Round Level mismatch: Expected {expected_tournament}, but got {actual_tournament}")


        if (not round.player_1) or (not round.player_2):
            actual_winner = round.winner
            if not round.player_1:
                expected_winner = round.player_2
            if not round.player_2:
                expected_winner = round.player_1
            self.test_case.assertEqual(expected_winner, actual_winner,
                                       f"Round Winner mismatch: Expected {expected_winner}, but got {actual_winner}")
        else:

            actual_winner = round.winner
            expected_winner = round.player_1
            expected_completed = True
            actual_completed = round.completed
            # print(f'player 1: {round.player_1}')
            # print(f'player 2: {round.player_2}')
            # print(f'round winner: {round.winner}')
            # print(f'match 1: {round.match.player_1}')
            # print(f'match 2: {round.match.player_2}')
            # print(f'match winmner: {round.match.winner}')
            # if round.level_num ==0:
            #     print(f'Match: {json.dumps(MatchSerializer(round.match).data, indent=4, cls=UUIDEncoder)}')


            self.test_case.assertEqual(expected_winner, actual_winner,
                                       f"Round Winner mismatch: Expected {expected_winner}, but got {actual_winner}")
            self.test_case.assertEqual(expected_completed, actual_completed, f"Round completed mismatch: Expected {expected_completed}, but got {actual_completed}")
            match = round.match
        # print(json.dumps(RoundSerializer(round).data, indent=4, cls=UUIDEncoder))



        # print(json.dumps(RoundSerializer(round).data,indent=4, cls=UUIDEncoder))
        # print(f'Round Recursion {round}')
        #
        # match = round.match
        # print(f'Match: {json.dumps(MatchSerializer(match).data,indent=4)}')


    def tournamentCheck(self,tournament,name, max_players):

        # print(json.dumps(TournamentSerializer(tournament).data,indent=4, cls=UUIDEncoder))



        expected_name = name
        actual_name = name

        self.test_case.assertEqual(expected_name, actual_name, f"Tournament Name mismatch: Expected {expected_name}, but got {actual_name}")

        expected_state = "completed"
        actual_state = tournament.state

        self.test_case.assertEqual(expected_state, actual_state, f"Tournament State mismatch: Expected {expected_state}, but got {actual_state}")

        expected_max_players = max_players
        actual_max_players = tournament.max_accepted_players

        self.test_case.assertEqual(expected_max_players, actual_max_players, f"Tournament Max Accepted Players mismatch: Expected {expected_max_players}, but got {actual_max_players}")

        final_round = tournament.final_round
        expected_final_round_level = 0
        actual_final_round_level = tournament.final_round.level_num
        self.test_case.assertEqual(expected_max_players, actual_max_players, f"Tournament Final Round Level mismatch: Expected {expected_final_round_level}, but got {actual_final_round_level}")
        # print(json.dumps(TournamentSerializer(tournament).data,indent=4, cls=UUIDEncoder))

        time.sleep(20)
        self.roundRecusion(round=final_round,level=expected_final_round_level,tournament=tournament)









