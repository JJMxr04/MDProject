# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
# from tests.tourneyTestHelpFuncs import TourneyTestHelp
from core.event.models.team import Team
# from tests.test1 import Test1
from tests.test2 import eventTest
from core.tournament.unit_tests.tests.Tourney_Simulator_1 import TourneyTest
# test1 = Test1()
eventTest = eventTest()
team1 = Team()
# from tests.Support import Support
# support = Support()

from core.event.models.sport import Sport
from core.event.serializers.sport import SportSerializer


if __name__ == '__main__':
    # test = TourneyTest(max_players=128,tourney_name='test1').run_test()
    print(SportSerializer(Sport.objects.get_by_key("americanfootball_nfl")).data)



    pass

