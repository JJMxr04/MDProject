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
    # match = Match.objects.get_object_by_id("7c57a214-de9e-4071-be84-312345c4f7f7")
    # print(json.dumps(MatchSerializer(match).data,indent=4))
    # team = Team.objects.get_object_by_public_id("01997853-4966-4526-b658-26e4e8a3fe7a")
    # team_name =  "Isaac Hardman"
    # team =Team.objects.get_object_by_team_name(team_name)
    # print(team)
    # print(json.dumps(TeamSerializer(team).data, indent=4))
    # team = Team.objects.get_object_by_team_id(338)
    # if Team.objects.get_object_by_team_id(338).exists():
    #     print(team)
    # team = Team.objects.filter(team_name="Isaac Hardman")
    # print(team)
    # events = Event.objects.filter(sport_key="mma_mixed_martial_arts").all()
    # for event in events:
    #     if event.home_team == "Sean O'Malley" and event.away_team == "Marlon Vera":
    #         print(event.id)
    #
    # event = Event.objects.get_object_by_id("48c8a16b-ddd6-5ebe-2dab-6e9428fff3b3")
    # event.completed = True
    # print(json.dumps(EventSerializer(event).data, indent = 4))
    # event.save()
    # games = Game.objects.filter(event=event).all()
    # print(games)

    pass


