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

def print_cron_jobs():
#     scheduler.print_jobs()
    print('Scheduled and  print cron job completed')

# def start_scheduler():
#
#     # scheduler.add_job(
#     #     complete_matches_cron,
#     #     trigger=IntervalTrigger(seconds=24*60*60),  # Run every 24 hours
#     #     id='complete_matches_cron',
#     #     name='Complete Matches Cron',
#     #     replace_existing=True,
#     # )
#     #
#     # scheduler.add_job(
#     #     tournament_cron_bracketMaker,
#     #     trigger=IntervalTrigger(seconds=24*60*60),  # Run every 24 hours
#     #     id='tournament_cron_bracketMaker',
#     #     name='Tournament Cron Bracket Maker',
#     #     replace_existing=True,
#     # )
#     #
#     # scheduler.add_job(
#     #     tournament_cron_2_day_reminder,
#     #     trigger=IntervalTrigger(seconds=24*60*60),  # Run every 24 hours
#     #     id='tournament_cron_2_day_reminder',
#     #     name='Tournament Cron 2 Day Reminder',
#     #     replace_existing=True,
#     # )
#     #
#     # scheduler.add_job(
#     #     sport_cron,
#     #     trigger=IntervalTrigger(seconds=24*60*60),  # Run every 24 hours
#     #     id='sport_cron',
#     #     name='Sport Cron Job',
#     #     replace_existing=True,
#     # )
#     #
#     # scheduler.add_job(
#     #     event_cron,
#     #     trigger=IntervalTrigger(seconds=6*60*60),  # Run every 6 hours
#     #     id='event_cron',
#     #     name='Event Cron Job',
#     #     replace_existing=True,
#     # )
#     #
#     # scheduler.add_job(
#     #     print_cron_jobs,
#     #     trigger=IntervalTrigger(seconds=1*60*60),  # Run every 1 hour
#     #     id='print_cron_jobs',
#     #     name='Print Cron Jobs',
#     #     replace_existing=True,
#     # )
#     #
#     if not scheduler.running:
#         scheduler.start()
#         print("Scheduler started successfully.")
