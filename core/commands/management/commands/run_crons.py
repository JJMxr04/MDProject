# scheduler_app/management/commands/runserver1.py
import sys
import threading
from django.core.management.commands.runserver import Command as BaseCommand
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger  # Add this line
from datetime import datetime
from core.event.crons.eventUpdate import EventCron

eventCron = EventCron()


class Command(BaseCommand):
    help = 'Runs the Crons along with the Django development server'
    print("Starting Crons")
    def run(self, *args, **options):
        # Start APScheduler in a separate thread
        scheduler_thread = threading.Thread(target=self.run_apscheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()

        # Call the original run method
        super().run(*args, **options)

    def run_apscheduler(self):
        scheduler = BackgroundScheduler()
        scheduler.start()

        def event_cron():
            eventCron.update_all_events()

        def print_cron_jobs():
            scheduler.print_jobs()


        scheduler.add_job(
            event_cron,
            trigger=IntervalTrigger(seconds=12*60*60),  # every 12 hours (Option A)
            id='event_cron',
            name='SofaScore event ingest',
            replace_existing=True,
        )

        scheduler.add_job(
            print_cron_jobs,
            trigger=IntervalTrigger(seconds=1*60*60),  # Run every 60 seconds
            id='print_cron_jobs',
            name='Print current time',
            replace_existing=True,
        )

        try:
            while True:
                # scheduler.print_jobs()
                scheduler._thread.join(1)
        except (KeyboardInterrupt, SystemExit):
            # Shut down the scheduler gracefully
            scheduler.shutdown()
            sys.exit(0)
