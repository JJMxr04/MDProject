# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
from core.match.models import Match
from core.mail import views
from core.auth.models import email
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron
from core.event.serializers.team import TeamSerializer

from core.event.models.event import Event
from core.event.models.team import Team
from django.http import Http404

from tests.test1 import Test1, Support
from tests.test2 import eventTest
from tests.test3 import testTeam
teamTest = testTeam()
test1 = Test1()
eventTest = eventTest()
team1 = Team()
support = Support()

# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize
import uuid
from rest_framework.response import Response
from rest_framework import status



def updateEvents():
    sportcron = SportCron()
    sportcron.get_sports()
    eventcron = EventCron()
    eventcron.update_all_events()
    support.datadump()



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    sport ={'key':"americanfootball_nfl",
            "group":"American Football",
            "title":"NFL",
            "description":"US Football",
            "active":True,
            "has_outrights":False,
            "created":"2024-01-31 07:15:05.409-05",
            "updated":"2024-01-31 07:15:05.409-05"
    }

    support.flush_database()
    print("starting first")
    eventTest.get_sport_events(sport,'nfl-copy1-1.json')
    print("starting second")
    eventTest.get_sport_events(sport,'nfl-copy2-1.json')

    print("starting Team Test")
    teamTest.test1()


    pass


