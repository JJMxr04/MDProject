# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
# from tests.tourneyTestHelpFuncs import TourneyTestHelp
from core.match.models import Match
from core.mail import views
from core.auth.models import email
from core.user.models import User
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron
from core.event.serializers.team import TeamSerializer
from core.tournament.serializers.tournament import TournamentSerializer, RoundSerializer
from core.event.models.event import Event
from core.event.models.team import Team
from core.tournament.models.tournament import Tournament, Round,InvitedPlayer, Player
from django.http import Http404
from datetime import datetime, timedelta
# from tests.test1 import Test1
from tests.test2 import eventTest
from tests.tourneyTest import TourneyTest
# test1 = Test1()
eventTest = eventTest()
team1 = Team()
# from tests.Support import Support
# support = Support()


if __name__ == '__main__':
    max_players = 128
    test = TourneyTest(max_players=max_players).run_test()




    pass

