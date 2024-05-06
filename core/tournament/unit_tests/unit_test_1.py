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
class TournamentCreationTestCase(TestCase):
    databases = ['default', 'test_mirror']

    def test_tournament_128(self):
        Support().load_data_sport_team()
        logger.info('Starting Tournament Simulation test with 128 max and accepted players')
        test = tournament_test_1(max_players=128, tourney_name='test128')


