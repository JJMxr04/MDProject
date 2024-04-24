# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()
from tests.tourneyTestHelpFuncs import TourneyTestHelp
from core.match.models import Match
from core.mail import views
from core.auth.models import email
from core.user.models import User
from core.event.crons.eventUpdate import EventCron
from core.event.crons.sportUpdate import SportCron
from core.event.serializers.team import TeamSerializer
from core.tournament.serializers.tournament import TournamentSerializer, RoundSerializer
from core.event.models.event import Event
from core.event.models.team import Team
from core.tournament.models.tournament import Tournament, Round,InvitedPlayer, Player
from django.http import Http404
from datetime import datetime, timedelta
from tests.test1 import Test1, Support
from tests.test2 import eventTest
test1 = Test1()
eventTest = eventTest()
team1 = Team()
support = Support()


if __name__ == '__main__':
    max_players = 129
    tourney_helper = TourneyTestHelp()
    tourney_helper.updateEvents()
    # tournament = tourney_helper.init_tournament(max_players=max_players)
    # tourney_helper.create_waitlistentry_and_users(max_players=max_players)
    # tourney_helper.tourney_invite_and_accept_players(tournament=tournament)
    # tourney_helper.make_tourney_rounds_matches(tournament=tournament)
    # tourney_helper.check_init_rounds_match_creation(tournament=tournament)




    pass

