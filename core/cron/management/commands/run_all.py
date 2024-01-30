from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Run both built-in and custom runserver commands'

    def handle(self, *args, **options):
        call_command('run_crons')
        # Run the built-in 'runserver' command
        call_command('runserver')

        # Run your custom 'runserver' command
        # call_command('runserver1', '--noreload')  # Add any additional options if needed
        # call_command('run_crons')