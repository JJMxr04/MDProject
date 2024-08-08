import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
import json

from dotenv import load_dotenv
load_dotenv()

from core.event.crons.eventUpdate import EventCron
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron

eventCron = EventCron()

if __name__ == '__main__':
    sportcron = SportCron()
    sportcron.get_sports()
    eventcron = EventCron()
    eventcron.update_all_events()
    # eventCron.get_upcoming_odds()