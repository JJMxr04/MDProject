# yourapp/tasks.py

from celery import shared_task
from time import sleep
# scheduler_app/scheduler.py

import threading
# from apscheduler.schedulers.background import BackgroundScheduler
# from apscheduler.triggers.interval import IntervalTrigger
from core.event.crons.sportUpdate import SportCron
from core.event.crons.eventUpdate import EventCron
from core.tournament.crons.BracketMaker import BracketMaker
from core.tournament.crons.TournamentReminder import Tournament2DayReminder
from core.match.crons.matchUpdate import MatchCron

sportCron = SportCron()
eventCron = EventCron()
matchCron = MatchCron()
# scheduler = BackgroundScheduler()

@shared_task
def complete_matches_cron():
    matchCron.completeMatches()

@shared_task
def tournament_cron_bracketMaker():
    BracketMaker.create_brackets()
@shared_task
def tournament_cron_2_day_reminder():
    Tournament2DayReminder.get_tournments_send_player_email()

@shared_task
def sport_cron():
    sportCron.get_sports()
@shared_task
def event_cron():
    eventCron.update_all_events()
@shared_task
def print_cron_jobs():
#     scheduler.print_jobs()
    print('Scheduled and  print cron job completed')

# @shared_task
# def add(x, y):
#     return x + y
#
# @shared_task
# def long_task(duration):
#     sleep(duration)
#     return 'Task completed'
