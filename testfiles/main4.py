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

from core.event.models.event import Event
from core.event.models.team import Team
from django.http import Http404

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



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    for x in range(121,220):
        WaitlistEntry.objects.create_entry(email=f"{x}test{x}@test.com", full_name=f"{x}test{x}")
    pass


