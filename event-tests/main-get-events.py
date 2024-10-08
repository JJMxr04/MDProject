import os
import django

# Set the environment variable for Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreRoot.settings')

# Initialize Django
django.setup()
from core.event.crons.sportUpdate import SportCron
from core.event.models.sport import Sport
from core.event.crons.eventUpdate import EventCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder
from core.match.crons.matchUpdate import MatchCron

sportCron = SportCron()
eventCron = EventCron()
matchCron = MatchCron()

def complete_matches_cron():
    matchCron.completeMatches()

def tournament_cron_bracketMaker():
    BracketMaker.create_brackets()

def tournament_cron_2_day_reminder():
    Tournament2DayReminder.get_tournments_send_player_email()

def sport_cron():
    sportCron.get_sports()

def event_cron():
    eventCron.update_all_events()




if __name__ == '__main__':

    sport_cron()
    event_cron()

    pass