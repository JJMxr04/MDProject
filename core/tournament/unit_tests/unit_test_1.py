import logging
import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from core.event.models.sport import Sport
from core.tournament.models.tournament import Round, RoundManager, Tournament, TournamentManager

# from core.tournament.unit_tests.tests.tournament_test_1 import tournament_test_1
from core.user.models import User

from .tests import tournament_test_1

logger = logging.getLogger(__name__)
from core.tournament.unit_tests.tests.Support import Support


class TournamentCreationTestCase(TestCase):
    databases = ['default', 'test_mirror']
    Support().load_data_sport_team()
    def test_tournament_128(self):
        Support().load_data_sport_team()
        x=128
        logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
        test = tournament_test_1(max_players=x, tourney_name=f'test{x}')

    # def test_tournament_64(self):
    #     x=64
    #     logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
    #     test = tournament_test_1(max_players=x, tourney_name=f'test{x}')
    #
    # def test_tournament_32(self):
    #     x=32
    #     logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
    #     test = tournament_test_1(max_players=x, tourney_name=f'test{x}')
    #
    # def test_tournament_16(self):
    #     x = 16
    #     logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
    #     test = tournament_test_1(max_players=x, tourney_name=f'test{x}')
    # def test_tournament_8(self):
    #     x=8
    #     logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
    #     test = tournament_test_1(max_players=x, tourney_name=f'test{x}')
    #
    # def test_tournament_4(self):
    #     x = 4
    #     logger.info(f'Starting Tournament Simulation test with {x} max and accepted players')
    #     test = tournament_test_1(max_players=x, tourney_name=f'test{x}')
    #
    #
    #
