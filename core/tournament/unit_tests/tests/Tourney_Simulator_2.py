# BIT-ROT: Same situation as Tourney_Simulator_1.py — see header there.
# Quarantined via core/tournament/unit_tests/__init__.py; no callers. Needs a
# rewrite against the new Selection-based pick API or deletion.

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
from core.event.serializers.event import EventSerializer

import os
import json

# Get the full path of the current file
current_file_path = __file__
current_file_directory = os.path.dirname(current_file_path)

# Define the base path relative to the test directory
base_test_path = os.path.abspath(current_file_directory)

from uuid import UUID

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super(UUIDEncoder, self).default(obj)


class TourneyTest:
    databases = ['default', 'test_mirror']

    def __init__(self,max_players,tourney_name):
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

        self.max_players = max_players
        self.tourney_name = tourney_name


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

    def update_file_commentment_times(self):
        #initial upload
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-1.json')
        self.support.modify_commencement_time_for_event(update_path_1, '484bc5582bb44ab79a1e942cf8762eda')
        # First Update
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-2.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy2-1.json')
        self.support.modify_commencement_time_for_event(update_path_2,'5e766a287ba24d40d9e40aa41efe19de')
        self.support.modify_commencement_time_for_event(update_path_3,'5e766a287ba24d40d9e40aa41efe19de')
        # Second Update
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-3.json')
        update_path_5 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy3-1.json')
        self.support.modify_commencement_time_for_event(update_path_4,'eb77c9dad13ef82ba5ff4dcf439d3bab')
        self.support.modify_commencement_time_for_event(update_path_5,'eb77c9dad13ef82ba5ff4dcf439d3bab')
        # Third Update
        update_path_6 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-4.json')
        update_path_7 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy4-1.json')
        self.support.modify_commencement_time_for_event(update_path_6,'b2eeb176fc9adfc63b9098b313905792')
        self.support.modify_commencement_time_for_event(update_path_7,'b2eeb176fc9adfc63b9098b313905792')
        # Forth Update
        update_path_8 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-5.json')
        update_path_9 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy5-1.json')
        self.support.modify_commencement_time_for_event(update_path_8,'d9498cb661062746dfc500a20c3a87e8')
        self.support.modify_commencement_time_for_event(update_path_9,'d9498cb661062746dfc500a20c3a87e8')
        #Fifth Update
        update_path_10 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-6.json')
        update_path_11 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy6-1.json')
        self.support.modify_commencement_time_for_event(update_path_10,'6cd4bff8b0950234be09e6c0acda7b95')
        self.support.modify_commencement_time_for_event(update_path_11,'6cd4bff8b0950234be09e6c0acda7b95')
        #Sixth Update
        update_path_12 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-7.json')
        update_path_13 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy7-1.json')
        self.support.modify_commencement_time_for_event(update_path_12,'53c6da53a7ba5f06aae182ee5ce38616')
        self.support.modify_commencement_time_for_event(update_path_13,'53c6da53a7ba5f06aae182ee5ce38616')
        # Seventh Update
        update_path_14 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy8-1.json')
        self.support.modify_commencement_time_for_event(update_path_14,'53c6da53a7ba5f06aae182ee5ce38616')


    def upload_test_events(self):
        # folder_path = os.path.join(base_test_path, 'test_files/originals')
        # output_file = os.path.join(base_test_path, 'test_files/sports_list.txt')
        # self.support.process_files_in_folder(folder_path, output_file)
        # sports = self.support.read_list_from_file(output_file)
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-1.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-1.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy2-1.json')
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2, "ea43090cd4cc2eb2fb98ba3847aba986")
        self.support.update_golden_game(update_path_3, "ea43090cd4cc2eb2fb98ba3847aba986")

    def update_test_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-2.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-2.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy3-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy2-1.json')

        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2, "c491f05b066449d95732c4f52ac57e66")
        self.support.update_golden_game(update_path_3, "c491f05b066449d95732c4f52ac57e66")
        self.support.test_get_nfl_events(update_path_4)
    def create_users(self):
        max_players = self.max_players
        for x in range(0, max_players):
            entry = WaitlistEntry.objects.get_object_by_email(f"{x}test{x}@test.com")
            if entry is None:
                entry = WaitlistEntry.objects.create_entry(email=f"{x}test{x}@test.com", full_name=f"{x}test{x}")
            entry = WaitlistEntry.objects.approve_waitlist_entry(entry.id)
            user = User.objects.get_object_by_email(f"{x}test{x}@test.com")
            if (user is Http404) and entry.admin_granted_access:
                User.objects.create_user(f"{x}test{x}", f"{x}test{x}@test.com", '1')

    def test_setup(self):
        self.support.updateSports()
        self.update_file_commentment_times()
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
        tournament = Tournament.objects.create(self.tourney_name, start_date, self.max_players)
        self.tournament_record = tournament


    def tourney_invite_and_accept_players(self):
        tournament = self.tournament_record
        for x in range(0, tournament.max_accepted_players):
            Tournament.objects.invite_player(tournament.id, f"{x}test{x}@test.com")
            user=User.objects.get_object_by_email(f"{x}test{x}@test.com")
            Invite = InvitedPlayer.objects.get(player=user,tournament=tournament)
            Tournament.objects.accept_invite(tournament.id, Invite)
        # Tournament.objects.make_init_matches(tournament)

    def make_tourney_rounds_matches(self):
        tournament = self.tournament_record
        Tournament.objects.bracket_maker(tournament)

    def make_tournament(self):
        # print(json.dumps(TournamentSerializer(self.tournament_record).data, indent=4, cls=UUIDEncoder))
        self.init_tournament()
        self.tourney_invite_and_accept_players()
        # print(json.dumps(TournamentSerializer(self.tournament_record).data, indent=4, cls=UUIDEncoder))
        self.make_tourney_rounds_matches()
        # print(json.dumps(TournamentSerializer(self.tournament_record).data,indent=4, cls=UUIDEncoder))

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
            # print(init_rounds)
            match = round.match
            if not match:
                continue
            if (not round.player_1) or (not round.player_2):
                print(json.dumps(RoundSerializer(round).data, indent=4, cls=UUIDEncoder))
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
            print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} next round players: {round.next_round.player_1.user} vs {round.next_round.player_2.user}')

    #  --- Initial Round Event Uploads---

    #  --- Second Round Event Uploads---
    def Simulate_Second_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 2)
        data1 = {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Philadelphia Eagles"
        }
        data2 = {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Buffalo Bills"
        }
        data1_gg = {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Kansas City Chiefs"
        }
        data2_gg = {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Las Vegas Raiders"
        }




        for round in init_rounds:

            # print(RoundSerializer(round).data)
            # print(RoundSerializer(round.prev_round_1).data)
            # print(round.prev_round_1.match.match_state)
            # print(RoundSerializer(round.prev_round_2).data)
            # print(round.prev_round_2.match.match_state)
            match = round.match
            if not match:
                continue
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
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-3.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-3.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy4-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy3-1.json')

        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2,
                                        "c1b7e562062eb3bac053a2f5ecf399f9")
        self.support.update_golden_game(update_path_3,
                                        "c1b7e562062eb3bac053a2f5ecf399f9")
        self.support.test_get_nfl_events(update_path_4)
    def print_second_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 2)

        for round in init_rounds:
            print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
            # print(f'match winner:{round.match.winner},  round winner: {round.winner.player} next round players: {round.next_round.player_1.player} vs {round.next_round.player_2.player}')


    #  --- Second Round Event Uploads---

    #  --- Third Round Event Uploads---
    def Simulate_Third_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 3)
        data1 = {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Baltimore Ravens"
        }
        data2 = {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Los Angeles Chargers"
        }
        data1_gg = {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Chicago Bears"
        }
        data2_gg = {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Minnesota Vikings"
        }

        for round in init_rounds:
            match = round.match
            if not match:
                continue
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

    def update_test_3_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-4.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-4.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy5-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy4-1.json')
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2,
                                        "76ae384526017414d68d617bf80b8aab")
        self.support.update_golden_game(update_path_3,
                                        "76ae384526017414d68d617bf80b8aab")
        self.support.test_get_nfl_events(update_path_4)
    def print_third_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 3)

        for round in init_rounds:
            print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} next round players: {round.next_round.player_1.player} vs {round.next_round.player_2.player}')


    #  --- Third Round Event Uploads---

    #  --- Forth Round Event Uploads---
    def Simulate_Fourth_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 4)
        data1 = {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Dallas Cowboys"
        }
        data2 = {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Seattle Seahawks"
        }
        data1_gg = {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Pittsburgh Steelers"
        }
        data2_gg = {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Arizona Cardinals"
        }

        for round in init_rounds:
            match = round.match
            if not match:
                continue
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

    def update_test_4_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-5.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-5.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy6-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy5-1.json')
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2,
                                        "41c4d77b6a910a6b2364fbeb51dba059")
        self.support.update_golden_game(update_path_3,
                                        "41c4d77b6a910a6b2364fbeb51dba059")
        self.support.test_get_nfl_events(update_path_4)
    def print_fourth_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 4)

        for round in init_rounds:
            print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} next round players: {round.next_round.player_1.player} vs {round.next_round.player_2.player}')


    #  --- Fourth Round Event Uploads---

    #  --- Fifth Round Event Uploads---
    def Simulate_Fifth_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 5)
        data1 = {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "New York Jets"
        }
        data2 = {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "Atlanta Falcons"
        }
        data1_gg = {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "New Orleans Saints"
        }
        data2_gg = {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "Detroit Lions"
        }

        for round in init_rounds:
            match = round.match
            if not match:
                continue
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

    def update_test_5_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-6.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-6.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy7-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy6-1.json')
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2,
                                        "5e0c5b79c3cb142f3361ade464174b68")
        self.support.update_golden_game(update_path_3,
                                        "5e0c5b79c3cb142f3361ade464174b68")
        self.support.test_get_nfl_events(update_path_4)

    def print_fifth_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 5)

        for round in init_rounds:
            print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} next round players: {round.next_round.player_1.player} vs {round.next_round.player_2.player}')

    #  --- Fifth Round Event Uploads---

    #  --- Sixth Round Event Uploads---
    def Simulate_Sixth_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 6)
        data1 = {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Tennessee Titans"
        }
        data2 = {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Indianapolis Colts"
        }
        data1_gg = {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Washington Commanders"
        }
        data2_gg = {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Miami Dolphins"
        }

        for round in init_rounds:
            match = round.match
            if not match:
                continue
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

    def update_test_6_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-7.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-7.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy8-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy7-1.json')
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2,
                                        "ad1bbe3e94716ca03c3059092cbd1eee")
        self.support.update_golden_game(update_path_3,
                                        "ad1bbe3e94716ca03c3059092cbd1eee")
        self.support.test_get_nfl_events(update_path_4)

    def print_sixth_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 6)

        for round in init_rounds:
            print( f'match winner:{round.match.winner}, round winner: {round.winner.player} ')
    #  --- Sixth Round Event Uploads---

    #  --- Sixth Round Event Uploads---
    def Simulate_Seventh_Round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 7)
        data1 = {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Houston Texans"
        }
        data2 = {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Denver Broncos"
        }
        data1_gg = {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "New England Patriots"
        }
        data2_gg = {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "Los Angeles Chargers"
        }

        for round in init_rounds:
            match = round.match
            if not match:
                continue
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

    def update_test_7_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy8-1.json')
        self.support.modify_commencement_time_for_event(update_path_1,'53c6da53a7ba5f06aae182ee5ce38616')

        self.support.test_get_nfl_events(update_path_1)

    def print_seventh_round(self):
        tournament = self.tournament_record
        init_rounds = Round.objects.get_tourney_level_rounds(tournament=tournament, level=tournament.levels - 7)

        for round in init_rounds:
            # print(f'Round level = {round.level_num}')
            # print(RoundSerializer(round).data)
            # print(MatchSerializer(round.match).data)
            print( f'match winner:{round.match.winner}, round winner: {round.winner} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')


    #  --- Seventh Round Event Uploads---


    # run rounds



    # run rounds

    def run_round_one(self):
        time.sleep(1)
        self.Simulate_First_Round()
        time.sleep(1)
        self.update_test_events()
        # time.sleep(1)
        # self.print_init_round()
        # time.sleep(1)

    def run_round_two(self):
        time.sleep(2)
        self.Simulate_Second_Round()
        time.sleep(2)
        self.update_test_2_events()
        # if self.tournament_record.levels == 2:
        #     time.sleep(1)
        #     self.print_second_round()
        # else:
        #     print(f'Second Round Finished')

    def run_round_three(self):
        time.sleep(6)
        self.Simulate_Third_Round()
        time.sleep(6)
        self.update_test_3_events()
        # if self.tournament_record.levels == 3:
        #     time.sleep(1)
        #     self.print_third_round()
        # else:
        #     print(f'Third Round Finished')

    def run_round_four(self):
        time.sleep(6)
        self.Simulate_Fourth_Round()
        time.sleep(6)
        self.update_test_4_events()
        # if self.tournament_record.levels == 4:
        #     time.sleep(1)
        #     self.print_fourth_round()
        # else:
        #     print(f'Forth Round Finished')
    def run_round_five(self):
        time.sleep(8)
        self.Simulate_Fifth_Round()
        time.sleep(8)
        self.update_test_5_events()
        # if self.tournament_record.levels == 5:
        #     time.sleep(1)
        #     self.print_fifth_round()
        # else:
        #     print(f'Fifth Round Finished')


    def run_round_six(self):
        time.sleep(12)
        self.Simulate_Sixth_Round()
        time.sleep(12)
        self.update_test_6_events()
        # if self.tournament_record.levels == 6:
        #     time.sleep(1)
        #     self.print_sixth_round()
        # else:
        #     print(f'Sixth Round Finished')

    def run_round_seven(self):
        time.sleep(18)
        self.Simulate_Seventh_Round()
        time.sleep(18)
        self.update_test_7_events()
        # if self.tournament_record.levels == 7:
        #     time.sleep(1)
        #     self.print_seventh_round()



    #  --- Run Test---

    def run_test(self):
        # print("starting test")
        self.test_setup()
        time.sleep(10)
        # print("Making Tourney")
        self.make_tournament()
        # print("Starting Rounds")
        self.run_round_one()
        if self.tournament_record.levels >= 2:
            self.run_round_two()
            # print("Finished Second Round")
        if self.tournament_record.levels >= 3:
            self.run_round_three()
            # print("Finished Third Round")
        if self.tournament_record.levels >= 4:
            self.run_round_four()
            # print("Finished Forth Round")
        if self.tournament_record.levels >= 5:
            self.run_round_five()
            # print("Finished Fifth Round")
        if self.tournament_record.levels >= 6:
            self.run_round_six()
            # print("Finished Sixth Round")
        if self.tournament_record.levels >= 7:
            self.run_round_seven()
            # print("Finished Seventh Round")

