# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
from core.match.models import Match
from core.mail import views
from core.auth.models import email


from tests.test1 import Test1, Support

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    Support.flush_database()
    player_1, player_2 = Support.get_test_players()

    match = Match.objects.create_match(player_1)


