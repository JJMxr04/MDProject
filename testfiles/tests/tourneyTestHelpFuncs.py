import os
from django import setup

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()

# Import necessary Django models, serializers, and other modules
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
from core.tournament.models.tournament import Tournament, Round, InvitedPlayer, Player
from django.http import Http404
from datetime import datetime, timedelta
from tests.test1 import Test1, Support
from tests.test2 import eventTest
from core.auth.models.waitlist import WaitlistEntry


class TourneyTestHelp:

    def __init__(self):
        # Initialize any required instances or variables
        self.test1 = Test1()
        self.eventTest = eventTest()
        self.team1 = Team()
        self.support = Support()

    def write_to_file(self, filename, text):
        with open(filename, 'a') as f:
            f.write(text + '\n')

    # Modify the print_tournament_bracket function to write to a file
    def write_tournament_bracket(self, current_round, filename, indent=0, level_width=4):
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
        self.write_to_file(filename,
                           f"{indentation}{horizontal_connector} Round {current_round.level_num}: {current_round}")

        # Recursive calls for previous rounds with updated indentation and connectors
        self.write_tournament_bracket(current_round.prev_round_1, filename, indent + level_width, level_width)
        self.write_tournament_bracket(current_round.prev_round_2, filename, indent + level_width, level_width)

    def updateEvents(self):
        sportcron = SportCron()
        sportcron.get_sports()
        eventcron = EventCron()
        eventcron.update_all_events()
        self.support.datadump()

    def next_week_start(self, date):
        # Add one week to the date
        next_week_date = date + timedelta(weeks=1)
        # Set the time to the beginning of the day
        next_week_start_date = next_week_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return next_week_start_date

    def create_waitlistentry_and_users(self, max_players):
        for x in range(0, max_players - 1):
            entry = WaitlistEntry.objects.get_object_by_email(f"{x}test{x}@test.com")
            if entry is None:
                print()
                entry = WaitlistEntry.objects.create_entry(email=f"{x}test{x}@test.com", full_name=f"{x}test{x}")
            WaitlistEntry.objects.approve_waitlist_entry(entry.id)
            user = User.objects.get_object_by_email(f"{x}test{x}@test.com")
            if user is Http404 and entry.admin_granted_access:
                User.objects.create_user(f"{x}test{x}", f"{x}test{x}@test.com", '1')

    def init_tournament(self, max_players):
        start_date = self.next_week_start(datetime.now())
        tournament = Tournament.objects.create('test1', start_date, max_players)
        return tournament

    def tourney_invite_and_accept_players(self, tournament):
        for x in range(0, tournament.max_accepted_players - 1):
            Tournament.objects.invitePlayer(tournament.id, f"{x}test{x}@test.com")
            Tournament.objects.acceptInvite(tournament.id, f"{x}test{x}@test.com")
        Tournament.objects.make_init_matches(tournament)

    def make_tourney_rounds_matches(self, tournament):
        Tournament.objects.create_rounds(tournament=tournament)
        Tournament.objects.make_init_matches(tournament)

    def check_round_dfs_creation(self, tournament):
        rounds = Round.objects.filter(tournament=tournament)

        level_counts = {level: 0 for level in range(8)}  # For rounds 0-7

        for round in rounds:
            level_counts[round.level_num] += 1

        for level, count in level_counts.items():
            print(f"Round {level}: {count}")

        final_round = tournament.final_round
        self.write_tournament_bracket(final_round, "bracket.txt", indent=0, level_width=10)

    def check_init_rounds_match_creation(self, tournament):
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 1)

        for round in init_rounds:
            print(RoundSerializer(round).data)
