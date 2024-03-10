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
from core.event.serializers.team import TeamSerializer
from core.match.serializers.match import MatchSerializer


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
    eventcron = EventCron()
    eventcron.update_all_events()
    # support.datadump()



# Press the green button in the gutter to run the script.
if __name__ == '__main__':


    # support.deleteExtraTeams()
    # updateEvents()
    # support.checkExtraTeams()
    # support.endEvents()
    # test1.testCreate20Matches()
    # test1.testCreateMatches(5)
    # team_name = "Aris Arguello"
    # team_search = Team.objects.filter(team_name=team_name)
    # print(team_search[0].team_id)

    # matches = Match.objects.filter(player_1="f7db283a-4cce-4f94-b5ae-096b43ec906f").all()
    # print(matches)
    # x = 0
    # y = 0
    # for match in matches:
    #     if match.match_state == "completed":
    #         x +=1
    #     else:
    #         y+=1
    #
    # print(x)
    # print(y)
    match = Match.objects.get_object_by_id("7c57a214-de9e-4071-be84-312345c4f7f7")
    print(json.dumps(MatchSerializer(match).data,indent=4))

    pass


