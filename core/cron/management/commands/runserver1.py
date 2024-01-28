# scheduler_app/management/commands/runserver1.py
import sys
import threading
from django.core.management.commands.runserver import Command as BaseCommand
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger  # Add this line
from datetime import datetime
# from core.event.crons.sportUpdate import SportCron
#
# sportCron = SportCron()
print("Executing runserver1.py")

class Command(BaseCommand):
    help = 'Runs the APScheduler along with the Django development server'

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

        def my_job():
            print("Job ran at: {}".format(datetime.now()))

        scheduler.add_job(
            my_job,
            trigger=IntervalTrigger(seconds=2),  # Run every 60 seconds
            id='my_job_id',
            name='Print current time',
            replace_existing=True,
        )

        try:
            while True:
                scheduler.print_jobs()
                scheduler._thread.join(1)
        except (KeyboardInterrupt, SystemExit):
            # Shut down the scheduler gracefully
            scheduler.shutdown()
            sys.exit(0)
