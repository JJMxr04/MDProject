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
from core.auth.models.waitlist import WaitlistEntry

def write_to_file(filename, text):
    with open(filename, 'a') as f:
        f.write(text + '\n')

# Modify the print_tournament_bracket function to write to a file
def write_tournament_bracket(current_round, filename, indent=0, level_width=4):
    """
    Recursively writes the tournament bracket in a top-down format to a file.
    """
    if current_round is None:
        return

    # If we're not at the root level, add a vertical connector to maintain continuity
    if indent > 0:
        connector = "|"
    else:
        connector = ""

    # Construct the indentation for proper alignment
    indentation = " " * (indent - 1) + connector
    horizontal_connector = "-" * (level_width - 1)  # Horizontal line length based on level width

    # Write the current round with the right spacing and connectors
    write_to_file(filename, f"{indentation}{horizontal_connector} Round {current_round.level_num}: {current_round}")

    # Recursive calls for previous rounds with updated indentation and connectors
    write_tournament_bracket(current_round.prev_round_1, filename, indent + level_width, level_width)
    write_tournament_bracket(current_round.prev_round_2, filename, indent + level_width, level_width)








def updateEvents():
    sportcron = SportCron()
    sportcron.get_sports()
    eventcron = EventCron()
    eventcron.update_all_events()
    support.datadump()

def next_week_start(date):
    # Add one week to the date
    next_week_date = date + timedelta(weeks=1)
    # Set the time to the beginning of the day
    next_week_start_date = next_week_date.replace(hour=0, minute=0, second=0, microsecond=0)
    return next_week_start_date

def create_waitlistentry_and_users(max_players):
    for x in range(0,max_players-1):
        entry = WaitlistEntry.objects.get_object_by_email(f"{x}test{x}@test.com")
        if ((entry is None)):
            WaitlistEntry.objects.create_entry(email=f"{x}test{x}@test.com", full_name=f"{x}test{x}")
            continue

        user = User.objects.get_object_by_email(f"{x}test{x}@test.com")

        if ((user is Http404) and (entry is not None) and (entry.admin_granted_access)):
            User.objects.create_user(f"{x}test{x}", f"{x}test{x}@test.com", '1')
            continue

def init_tournament(max_players):
    start_date = next_week_start(datetime.now())
    tournament = Tournament.objects.create('test1', start_date, max_players)
    return tournament

def tourney_invite_and_accect_players(tournament):
    for x in range(0, tournament.max_accepted_players-1):
        Tournament.objects.invitePlayer(tournament.id, f"{x}test{x}@test.com" )
        Tournament.objects.acceptInvite(tournament.id, f"{x}test{x}@test.com" )
    Tournament.objects.make_init_matches(tournament)
def make_tourney_rounds_matches(tournament):
    Tournament.objects.create_rounds(tournament=tournament)
    Tournament.objects.make_init_matches(tournament)
    pass
def check_round_dfs_creation(torunament):
    rounds = Round.objects.filter(tournament=tournament)

    round0 = 0
    round1 = 0
    round2 = 0
    round3 = 0
    round4 = 0
    round5 = 0
    round6 = 0
    round7 = 0
    # print(rounds)
    for round in rounds:
        if round.level_num == 0:
            round0 += 1
        if round.level_num == 1:
            round1 += 1
        if round.level_num == 2:
            round2 += 1
        if round.level_num == 3:
            round3 += 1
        if round.level_num == 4:
            round4 += 1
        if round.level_num == 5:
            round5 += 1
        if round.level_num == 6:
            round6 += 1
        if round.level_num == 7:
            round7 += 1
        # print(f"Level:{round.level_num}: {RoundSerializer(round).data}")

    print(f"round 0:{round0}")
    print(f"round 1:{round1}")
    print(f"round 2:{round2}")
    print(f"round 3:{round3}")
    print(f"round 4:{round4}")
    print(f"round 5:{round5}")
    print(f"round 6:{round6}")
    print(f"round 7:{round7}")

    final_round = tournament.final_round
    # print(final_round)
    write_tournament_bracket(final_round, indent=0, level_width=10)

def check_init_rounds_match_creation(tournament):
    init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament,level=tournament.levels-1)

    for round in init_rounds:
        print(RoundSerializer(round).data)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    max_players = 129
    tournament = init_tournament(max_players=max_players)
    # print(tournament.max_accepted_players)
    # print(len(list(Player.objects.filter(tournament=tournament))))
    create_waitlistentry_and_users(max_players=max_players)
    # print(tournament.max_accepted_players)
    # print(len(list(Player.objects.filter(tournament=tournament))))
    tourney_invite_and_accect_players(tournament=tournament)
    # print(tournament.max_accepted_players)
    # print(len(list(Player.objects.filter(tournament=tournament))))
    make_tourney_rounds_matches(tournament=tournament)
    check_init_rounds_match_creation(tournament=tournament)




    pass

