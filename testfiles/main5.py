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
from core.user.models import User
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron
from core.event.serializers.team import TeamSerializer
from core.tournament.serializers.tournament import TournamentSerializer
from core.event.models.event import Event
from core.event.models.team import Team
from core.tournament.models.tournament import Tournament, Round
from django.http import Http404
from datetime import datetime, timedelta
from tests.test1 import Test1, Support
from tests.test2 import eventTest
test1 = Test1()
eventTest = eventTest()
team1 = Team()
support = Support()
from core.auth.models.waitlist import WaitlistEntry





def updateEvents():
    sportcron = SportCron()
    sportcron.get_sports()
    eventcron = EventCron()
    eventcron.update_all_events()
    support.datadump()

def next_week_start(date):
    # Add one week to the date
    next_week_date = date + timedelta(weeks=1)
    # Set the time to the beginning of the day
    next_week_start_date = next_week_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return next_week_start_date

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # start = next_week_start(datetime.now())
    # tournament = Tournament.objects.create(name="Test1 Tourney", start_date=start,max_accepted_players=128)
    # tournament = Tournament.objects.get_object_by_id("1d1debb5-86d3-40e6-8f39-0a3a6f6dfb89")
    # for
    # serializer = TournamentSerializer(tournament)
    # print(serializer.data)


    pass


