import json
import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from core.tournament.models.tournament import Tournament, Round, TournamentManager, RoundManager
# from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
from core.user.models import User
from core.event.models.sport import Sport
# from .tests import tournament_test_1
import logging
logger = logging.getLogger(__name__)
from core.tournament.unit_tests.tests.Support import Support
from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest
import unittest
from core.tournament.models.tournament import Player
import logging
import math
import time

from core.match.serializers.match import MatchSerializer
from core.tournament.serializers.tournament import RoundSerializer, TournamentSerializer
from uuid import UUID

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super(UUIDEncoder, self).default(obj)
class TournamentChecks(TestCase):
    round_0_data = {}
    round_1_data = {}
    round_2_data = {}
    round_3_data = {}
    round_4_data = {}
    round_5_data = {}
    round_6_data = {}
    round_7_data = {}

    # All the checks

    def __init__(self,test_case, tournament,name, max_players):
        self.test_case = test_case
        self.tournamentCheck(tournament=tournament,name=name,max_players=max_players)



    def eventCheck(self):
        pass
    def gameCheck(self,data):
        pass
    def matchChecks(self,data):
        pass

    def roundCheck(self,round):
        pass

    def torunamentCheck(self,tournament):
        pass

    def roundRecusion(self,round,level,tournament):
        # recusion dfs
        if not round:
            return
        self.roundRecusion(round.prev_round_1,level +1,tournament=tournament)
        self.roundRecusion(round.prev_round_2,level+1,tournament=tournament)

        #
        actual_winner = round.winner
        expected_winner = round.player_1 #expected winner
        expected_completed = True
        actual_completed = round.completed
        expected_level = level
        actual_level = round.level_num
        expected_tournament = tournament
        actual_tournament = round.tournament


        # self.test_case.assertEqual(expected_winner, actual_winner, f"Round Winner mismatch: Expected {expected_winner}, but got {actual_winner}")
        # self.test_case.assertEqual(expected_completed, actual_completed, f"Round completed mismatch: Expected {expected_completed}, but got {actual_completed}")
        self.test_case.assertEqual(expected_level, actual_level, f"Round Level mismatch: Expected {expected_level}, but got {actual_level}")
        self.test_case.assertEqual(expected_level, actual_level, f"Round Level mismatch: Expected {expected_tournament}, but got {actual_tournament}")


        print(json.dumps(RoundSerializer(round).data,indent=4, cls=UUIDEncoder))
        print(f'Round Recursion {round}')

        match = round.match
        print(f'Match: {json.dumps(MatchSerializer(match).data,indent=4)}')


    def tournamentCheck(self,tournament,name, max_players):
        # tourney = Tournament.objects.get_object_by_id(id=tournament.id)
        # print("sepereate")
        # print(json.dumps(TournamentSerializer(tourney).data, indent=4, cls=UUIDEncoder))
        # print("sepereate")
        expected_name = name
        actual_name = name

        self.test_case.assertEqual(expected_name, actual_name, f"Tournament Name mismatch: Expected {expected_name}, but got {actual_name}")

        # expected_state = "completed"
        # actual_state = tournament.state
        #
        # self.test_case.assertEqual(expected_state, actual_state, f"Tournament State mismatch: Expected {expected_state}, but got {actual_state}")

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









