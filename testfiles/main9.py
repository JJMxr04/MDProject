# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
# from tests.tourneyTestHelpFuncs import TourneyTestHelp
from tests.tests.tournament_test_2 import tournament_test_3
from tests.tests.tourney_checks import TournamentChecks
from tests.tests.Support import Support
from core.tournament.models.tournament import Tournament
# from tests.tests.tournament_test_3 import TourneyTest
from core.event.serializers.sport import SportSerializer
import math
import time
import logging
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    # test = TourneyTest(max_players=128,tourney_name='test1').run_test()
    expected_max_players = 128
    logger.info(f'Starting Tournament Simulation test with {expected_max_players} max and accepted players')
    Support().load_data_sport_team()
    expected_name = f'test{expected_max_players}'
    expected_levels = math.log2(expected_max_players)
    test = tournament_test_3(max_players=expected_max_players, tourney_name=expected_name)
    # time.sleep(30)
    # tournament = Tournament.objects.get_object_by_id(id=test.tournament.id)


    logger.info(f'Finished Tournament Simulation test with {expected_max_players} max and accepted players')



    pass

