# myapp/management/commands/reset_db.py

from django.core.management.base import BaseCommand
from django.db import connections, transaction

class Command(BaseCommand):
    help = 'Reset the database by dropping and recreating all tables'

    def handle(self, *args, **options):
        # Iterate through each database connection
        for alias in connections:
            connection = connections[alias]
            cursor = connection.cursor()

            try:
                self.stdout.write(self.style.SUCCESS(f'Resetting database {alias}...'))

                # Get all table names from the current database
                cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")
                tables = [table[0] for table in cursor.fetchall()]

                # Drop all tables
                for table in tables:
                    cursor.execute(f'DROP TABLE IF EXISTS {table} CASCADE;')

                # Commit the changes
                transaction.commit()

            finally:
                # Commit the changes
                transaction.commit()

        self.stdout.write(self.style.SUCCESS('Database reset complete.'))
