# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
import json
from core.match.models import Match
from core.mail import views
from core.auth.models import email
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron
from core.event.serializers.event import EventSerializer
from core.event.serializers.team import TeamSerializer
from core.match.serializers.match import MatchSerializer
from core.game.models import Game
from core.event.models.sport import Sport



from core.event.models.event import Event
from core.event.models.team import Team
from django.http import Http404

from tests.test1 import Test1, Support
test1 = Test1()
team1 = Team()
support = Support()


def updateEvents():
    sportcron = SportCron()
    sportcron.get_sports()
    # eventcron = EventCron()
    # eventcron.update_all_events()
    # support.datadump()



# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    updateEvents()
    # print(Sport.objects.filter())


    pass


