import uuid
from datetime import datetime, timedelta
from django.test import TestCase
from core.tournament.models.tournament import Tournament, Round, TournamentManager, RoundManager
# from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
from core.user.models import User
from core.event.models.sport import Sport
from .tests import tournament_test_1
import logging
logger = logging.getLogger(__name__)
from core.tournament.unit_tests.tests.Support import Support
from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest
import unittest
from core.tournament.models.tournament import Player
import logging
import math
class TournamentChecks:
    round_0_data = {}
    round_1_data = {}
    round_2_data = {}
    round_3_data = {}
    round_4_data = {}
    round_5_data = {}
    round_6_data = {}
    round_7_data = {}

    # All the checks 


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

    def roundRecusion(self,round):
        pass



