from django.core.management.base import BaseCommand
from django.db import connections, transaction


class Command(BaseCommand):
    help = 'Flush all databases except for specific tables'

    def add_arguments(self, parser):
        parser.add_argument('exclude_tables', nargs='+', type=str, help='List of tables to exclude from flushing')

    def handle(self, *args, **options):
        exclude_tables = options['exclude_tables']

        # Iterate through each database connection
        for alias in connections:
            connection = connections[alias]
            cursor = connection.cursor()

            self.stdout.write(self.style.SUCCESS(f'Flushing database {alias} except for tables {exclude_tables}...'))

            # Get all table names from the current database
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")
            tables = [table[0] for table in cursor.fetchall()]

            # Remove the specified tables from the list
            tables = [table for table in tables if table not in exclude_tables]

            # Use a single atomic block to handle the entire transaction
            with transaction.atomic():
                # Truncate all remaining tables
                for table in tables:
                    cursor.execute(f'TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;')

        self.stdout.write(self.style.SUCCESS('Database flushing complete.'))
