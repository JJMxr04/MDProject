from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Create Portal Group if it does not exist'

    def handle(self, *args, **kwargs):
        portal_group, created = Group.objects.get_or_create(name='Portal Group')
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created Portal Group'))
        else:
            self.stdout.write(self.style.WARNING('Portal Group already exists'))
