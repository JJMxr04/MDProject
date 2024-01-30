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


from tests.test1 import Test1, Support
test1 = Test1()
support = Support()

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # test1.test9()

    # test1.test10()
    # test1.testFlushAndGetSportsAndEvents()
    # sportcron = SportCron()
    # sportcron.get_sports()
    # eventcron = EventCron()
    # eventcron.update_all_events()
    # support.flush_database()
    pass


