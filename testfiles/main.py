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
test1 = Test1()
team1 = Team()
support = Support()

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # test1.test9()
    # support.datadump()
    # test1.test10()
    # test1.testFlushAndGetSportsAndEvents()
    # sportcron = SportCron()
    # sportcron.get_sports()
    # eventcron = EventCron()
    # eventcron.update_all_events()
    # Team.objects.get(team_name="Ibraheem Sulaimaan")
    # teams = Team.objects.all()
    # for team in teams:
    #     name = team.team_name
    #
    #     teams1 = Team.objects.filter(team_name=name)
    #     if len(teams1) > 1:
    #         print(f"{name} has {len(teams1)} item")
    #         teams1[1].delete()
    # support.flush_database()
    # test1.testTeams("Dayton Flyers","NCAAB","Basketball")
    # print(Event.objects.get_object_by_id("8b40c3fc8c994eb271a7980fbc27802e"))
    #support.flush_database()
    # print(Team.objects.get_object_by_team_name("Richmond Spiders"))
    # support.datadump()
    # support.endEvents()
    # test1.testCreate20Matches()

    pass


