import os
import time

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
from core.game.models.game import Game
from core.event.models.sport import Sport
from core.tournament.models.tournament import Tournament, Round, InvitedPlayer, Player
from django.http import Http404
from datetime import datetime, timedelta
from .Support import Support
# from tests.test2 import eventTest
from core.auth.models.waitlist import WaitlistEntry
# from .tourneyTestHelpFuncs import TourneyTestHelp
from core.match.serializers.match import MatchSerializer


class TourneyTest:

    def __init__(self):
        # Initialize any required instances or variables
        self.support = Support()
        # self.tourney_helper = TourneyTestHelp()
        self.tournament_record = None
        self.tournament = Tournament()
        self.match = Match()
        self.game = Game()
        self.event = Event()
        self.team = Team()
        self.sport = Sport()

        self.max_players = 128


    # Non test Functions
    def write_to_file(self, filename, text):
        with open(filename, 'a') as f:
            f.write(text + '\n')

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



    # Test Functions
    #  --- Setup---
    def flush_tables(self):
        self.support.datadump()
        self.support.flush_database()

    def upload_test_events(self):
        folder_path = 'originals'
        output_file = 'sports_list.txt'
        self.support.process_files_in_folder(folder_path, output_file)
        sports = self.support.read_list_from_file(output_file)
        self.support.test_get_nfl_events(f'nfl-copy1-1.json')
        self.support.update_golden_game(f'nfl-copy1-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
        self.support.update_golden_game(f'nfl-copy2-1.json', "ea43090cd4cc2eb2fb98ba3847aba986")
    def update_test_events(self):
        self.support.test_get_nfl_events(f'nfl-copy2-1.json')

    def create_users(self):
        max_players = self.max_players
        for x in range(0, max_players - 1):
            entry = WaitlistEntry.objects.get_object_by_email(f"{x}test{x}@test.com")
            if entry is None:
                entry = WaitlistEntry.objects.create_entry(email=f"{x}test{x}@test.com", full_name=f"{x}test{x}")
            entry = WaitlistEntry.objects.approve_waitlist_entry(entry.id)
            user = User.objects.get_object_by_email(f"{x}test{x}@test.com")
            if (user is Http404) and entry.admin_granted_access:
                User.objects.create_user(f"{x}test{x}", f"{x}test{x}@test.com", '1')

    def test_setup(self):
        self.flush_tables()
        self.upload_test_events()
        self.create_users()

    #  --- Setup---

    #  --- tournament creation---

    def tourney_next_week_start(self, date):
        # Add one week to the date
        next_week_date = date + timedelta(weeks=1)
        # Set the time to the beginning of the day
        next_week_start_date = next_week_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return next_week_start_date

    def init_tournament(self):
        start_date = self.tourney_next_week_start(datetime.now())
        tournament = Tournament.objects.create('test1', start_date, self.max_players)
        self.tournament_record = tournament


    def tourney_invite_and_accept_players(self):
        tournament = self.tournament_record
        for x in range(0, tournament.max_accepted_players):
            Tournament.objects.invitePlayer(tournament.id, f"{x}test{x}@test.com")
            Tournament.objects.acceptInvite(tournament.id, f"{x}test{x}@test.com")
        Tournament.objects.make_init_matches(tournament)

    def make_tourney_rounds_matches(self):
        tournament = self.tournament_record
        Tournament.objects.create_rounds(tournament=tournament)
        Tournament.objects.make_init_matches(tournament)

    def make_tournament(self):
        self.init_tournament()
        self.tourney_invite_and_accept_players()
        self.make_tourney_rounds_matches()

    #  --- tournament creation---
    def update_match(self,match,data,player):
        if match.player_1 == player:
            if match.player_1_game_1.event == None:
                Game.objects.update_by_id(match.player_1_game_1.id, player, data)
            if match.player_1_game_2.event == None:
                Game.objects.update_by_id(match.player_1_game_2.id, player, data)
            if match.player_1_game_3.event == None:
                Game.objects.update_by_id(match.player_1_game_3.id, player, data)
            if match.player_1_game_4.event == None:
                Game.objects.update_by_id(match.player_1_game_4.id, player, data)
            if match.player_1_game_5.event == None:
                Game.objects.update_by_id(match.player_1_game_5.id, player, data)
        if match.player_2 == player:
            if match.player_2_game_1.event == None:
                Game.objects.update_by_id(match.player_2_game_1.id, player, data)
            if match.player_2_game_2.event == None:
                Game.objects.update_by_id(match.player_2_game_2.id, player, data)
            if match.player_2_game_3.event == None:
                Game.objects.update_by_id(match.player_2_game_3.id, player, data)
            if match.player_2_game_4.event == None:
                Game.objects.update_by_id(match.player_2_game_4.id, player, data)
            if match.player_2_game_5.event == None:
                Game.objects.update_by_id(match.player_2_game_5.id, player, data)

    #  --- Initial Round Event Uploads---
    def Simulate_First_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 1)
        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }
        data1_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        }
        data2_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }


        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player
            for x in range(0,5):
                self.update_match(match,data1,user_1)
                self.update_match(match,data2,user_2)
            Game.objects.update_by_id(match.player_1_game_1.id,user_2,data2)
            Game.objects.update_by_id(match.player_1_game_2.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_3.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_4.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_5.id, user_2, data2)

            Game.objects.update_by_id(match.player_2_game_1.id,user_1,data1)
            Game.objects.update_by_id(match.player_2_game_2.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_3.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_4.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_5.id, user_1, data1)

            Game.objects.update_by_id(match.golden_game.id, user_1, data1_gg)
            Game.objects.update_by_id(match.golden_game.id, user_2, data2_gg)

    def print_init_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 1)

        for round in init_rounds:
            # print('round')
            # print(RoundSerializer(round).data)
            # print('match')
            # print(MatchSerializer(round.match).data)
            print(f'match winner:{round.match.winner}, round winner: {round.winner} next round players: {round.next_round.player_1} vs {round.next_round.player_2}')

    #  --- Initial Round Event Uploads---

    #  --- Second Round Event Uploads---
    def Simulate_Second_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 2)
        data1 = {
            "event_id": "123e4567e89b12d3a456426655440000",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "123e4567e89b12d3a456426655440000",
            "player_choice": "Tennessee Titans"
        }
        data1_gg = {
            "event_id": "89b132d3e4567e98a123456755440000",
            "player_choice": "New York Giants"
        }
        data2_gg = {
            "event_id": "89b132d3e4567e98a123456755440000",
            "player_choice": "Green Bay Packers"
        }


        for round in init_rounds:
            print(RoundSerializer(round).data)
            print(RoundSerializer(round.prev_round_1).data)
            print(round.prev_round_1.match.match_state)
            print(RoundSerializer(round.prev_round_2).data)
            print(round.prev_round_2.match.match_state)
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player
            for x in range(0,5):
                self.update_match(match,data1,user_1)
                self.update_match(match,data2,user_2)
            Game.objects.update_by_id(match.player_1_game_1.id,user_2,data2)
            Game.objects.update_by_id(match.player_1_game_2.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_3.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_4.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_5.id, user_2, data2)

            Game.objects.update_by_id(match.player_2_game_1.id,user_1,data1)
            Game.objects.update_by_id(match.player_2_game_2.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_3.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_4.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_5.id, user_1, data1)

            Game.objects.update_by_id(match.golden_game.id, user_1, data1_gg)
            Game.objects.update_by_id(match.golden_game.id, user_2, data2_gg)

    def update_test_2_events(self):
        self.support.test_get_nfl_events(f'nfl-copy3-1.json')
    def print_second_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 2)

        for round in init_rounds:
            # print('round')
            # print(RoundSerializer(round).data)
            # print('match')
            # print(MatchSerializer(round.match).data)
            print(f'match winner:{round.match.winner}, round winner: {round.winner} next round players: {round.next_round.player_1} vs {round.next_round.player_2}')


    #  --- Second Round Event Uploads---

    #  --- Third Round Event Uploads---
    def Simulate_Third_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 2)
        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }
        data1_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        }
        data2_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }

        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player
            for x in range(0, 5):
                self.update_match(match, data1, user_1)
                self.update_match(match, data2, user_2)
            Game.objects.update_by_id(match.player_1_game_1.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_2.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_3.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_4.id, user_2, data2)
            Game.objects.update_by_id(match.player_1_game_5.id, user_2, data2)

            Game.objects.update_by_id(match.player_2_game_1.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_2.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_3.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_4.id, user_1, data1)
            Game.objects.update_by_id(match.player_2_game_5.id, user_1, data1)

            Game.objects.update_by_id(match.golden_game.id, user_1, data1_gg)
            Game.objects.update_by_id(match.golden_game.id, user_2, data2_gg)

    #  --- Third Round Event Uploads---



    #  --- Run Test---

    def run_test(self):
        self.test_setup()
        time.sleep(1)
        self.make_tournament()
        time.sleep(1)
        self.Simulate_First_Round()
        time.sleep(1)
        self.update_test_events()
        time.sleep(1)
        # self.print_init_round()
        # time.sleep(1)
        self.Simulate_Second_Round()
        time.sleep(1)
        self.update_test_2_events()
        time.sleep(1)
        self.print_second_round()
        # time.sleep(1)


