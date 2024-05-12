import os
import asyncio
import aiofiles
import logging
from django import setup
from datetime import datetime, timedelta

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
from .Support import Support
from core.auth.models.waitlist import WaitlistEntry
from core.match.serializers.match import MatchSerializer
from core.event.serializers.event import EventSerializer

# Setup logging
logging.basicConfig(level=logging.INFO)

# Base file paths
current_file_path = __file__
current_file_directory = os.path.dirname(current_file_path)
base_test_path = os.path.abspath(current_file_directory)

class TourneyTest:
    databases = ['default', 'test_mirror']

    def __init__(self, max_players, tourney_name):
        self.support = Support()
        self.tournament_record = None
        self.tournament = Tournament()
        self.match = Match()
        self.game = Game()
        self.event = Event()
        self.team = Team()
        self.sport = Sport()
        self.max_players = max_players
        self.tourney_name = tourney_name

    # Asynchronous writing to a file
    async def async_write_to_file(self, filename, text):
        async with aiofiles.open(filename, 'a') as f:
            await f.write(text + '\n')

    # Asynchronous write of tournament bracket
    async def async_write_tournament_bracket(self, current_round, filename, indent=0, level_width=4):
        if current_round is None:
            return

        connector = "|" if indent > 0 else ""
        indentation = " " * (indent - 1) + connector
        horizontal_connector = "-" * (level_width - 1)  # Horizontal line length based on level width

        await self.async_write_to_file(
            filename,
            f"{indentation}{horizontal_connector} Round {current_round.level_num}: {current_round}",
        )

        await self.async_write_tournament_bracket(
            current_round.prev_round_1, filename, indent + level_width, level_width
        )
        await self.async_write_tournament_bracket(
            current_round.prev_round_2, filename, indent + level_width, level_width
        )

    # Test Functions
    # --- Setup ---
    async def flush_tables(self):
        await asyncio.to_thread(self.support.datadump)
        await asyncio.to_thread(self.support.flush_database)

    # Asynchronous test event upload
    async def upload_test_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-1.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-1.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy2-1.json')

        await asyncio.to_thread(self.support.test_get_nfl_events, update_path_1)
        await asyncio.to_thread(self.support.update_golden_game, update_path_2, "ea43090cd4cc2eb2fb98ba3847aba986")
        await asyncio.to_thread(self.support.update_golden_game, update_path_3, "ea43090cd4cc2eb2fb98ba3847aba986")

    # Asynchronous test event update
    async def update_test_events(self):
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-2.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-2.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy3-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy2-1.json')

<<<<<<< Updated upstream
        await asyncio.to_thread(self.support.test_get_nfl_events, update_path_1)
        await asyncio.to_thread(self.support.update_golden_game, update_path_2, "c491f05b066449d95732c4f52ac57e66")
        await asyncio.to_thread(self.support.update_golden_game, update_path_3, "c491f05b066449d95732c4f52ac57e66")
        await asyncio.to_thread(self.support.test_get_nfl_events, update_path_4)

    # Asynchronous user creation
    async def create_users(self):
        for x in range(self.max_players):
            email = f"{x}test{x}@test.com"
            entry = await asyncio.to_thread(WaitlistEntry.objects.get_object_by_email, email)
=======
        self.support.test_get_nfl_events(update_path_1)
        self.support.update_golden_game(update_path_2, "c491f05b066449d95732c4f52ac57e66")
        self.support.update_golden_game(update_path_3, "c491f05b066449d95732c4f52ac57e66")
        self.support.test_get_nfl_events(update_path_4)
    def create_users(self):
        max_players = self.max_players
        for x in range(0, max_players):
            entry = WaitlistEntry.objects.get_object_by_email(f"{x}test{x}@test.com")
>>>>>>> Stashed changes
            if entry is None:
                entry = await asyncio.to_thread(WaitlistEntry.objects.create_entry, email=email, full_name=f"{x}test{x}")
            await asyncio.to_thread(WaitlistEntry.objects.approve_waitlist_entry, entry.id)

            user = await asyncio.to_thread(User.objects.get_object_by_email, email)
            if isinstance(user, Http404):
                if entry.admin_granted_access:
                    await asyncio.to_thread(User.objects.create_user, f"{x}test{x}", email, '1')

    # Asynchronous test setup
    async def test_setup(self):
        await self.support.updateSports()
        await self.upload_test_events()
        await self.create_users()
    #  --- Setup---

    #  --- tournament creation ---
    async def tourney_next_week_start(self, date):
        next_week_date = date + timedelta(weeks=1)
        next_week_start_date = next_week_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return next_week_start_date

    async def init_tournament(self):
        start_date = self.tourney_next_week_start(datetime.now())
        self.tournament_record = await asyncio.to_thread(
            Tournament.objects.create,
            self.tourney_name,
            start_date,
            self.max_players,
        )

    async def tourney_invite_and_accept_players(self):
        tournament = self.tournament_record
        tasks = []
        for x in range(0, tournament.max_accepted_players):
            email = f"{x}test{x}@test.com"
            tasks.append(
                asyncio.to_thread(Tournament.objects.invitePlayer, tournament.id, email)
            )
            tasks.append(
                asyncio.to_thread(Tournament.objects.acceptInvite, tournament.id, email)
            )
        await asyncio.gather(*tasks)
        await asyncio.to_thread(Tournament.objects.make_init_matches, tournament)

    async def make_tourney_rounds_matches(self):
        tournament = self.tournament_record
        await asyncio.to_thread(Tournament.objects.create_rounds, tournament=tournament)
        await asyncio.to_thread(Tournament.objects.make_init_matches, tournament)

    async def make_tournament(self):
        await self.init_tournament()
        await self.tourney_invite_and_accept_players()
        await self.make_tourney_rounds_matches()
    #  --- tournament creation ---

    # Asynchronous match update
    async def async_update_match(self, match, data, player):
        tasks = []
        if match.player_1 == player:
            if not match.player_1_game_1.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, player, data))
            if not match.player_1_game_2.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, player, data))
            if not match.player_1_game_3.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, player, data))
            if not match.player_1_game_4.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, player, data))
            if not match.player_1_game_5.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, player, data))

        if match.player_2 == player:
            if not match.player_2_game_1.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, player, data))
            if not match.player_2_game_2.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, player, data))
            if not match.player_2_game_3.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, player, data))
            if not match.player_2_game_4.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, player, data))
            if not match.player_2_game_5.event:
                tasks.append(asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, player, data))

        await asyncio.gather(*tasks)

    # Asynchronous simulation of the first round
    async def async_simulate_first_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 1,
        )

        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins",
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans",
        }
        data1_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants",
        }
        data2_gg = {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers",
        }

        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Async match updates
            tasks.append(self.async_update_match(match, data1, user_1))
            tasks.append(self.async_update_match(match, data2, user_2))

            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        await asyncio.gather(*tasks)

    # Asynchronous print function for initial round
    # Asynchronous print function for the initial round
    async def async_print_init_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 1,
        )

        # Asynchronous loop to print round information
        for round in init_rounds:
            print(f"Match winner: {round.match.winner}, Round winner: {round.winner.player}")

    #  --- Initial Round Event Uploads---

    #  --- Second Round Event Uploads---
        async def async_simulate_second_round(self):
            tournament = self.tournament_record
            init_rounds = await asyncio.to_thread(
                Round.objects.get_tourney_level_rounds,
                tournament=tournament,
                level=tournament.levels - 2,
            )

            data1 = {
                "event_id": "5e766a287ba24d40d9e40aa41efe19de",
                "player_choice": "Philadelphia Eagles",
            }
            data2 = {
                "event_id": "5e766a287ba24d40d9e40aa41efe19de",
                "player_choice": "Buffalo Bills",
            }
            data1_gg = {
                "event_id": "c491f05b066449d95732c4f52ac57e66",
                "player_choice": "Kansas City Chiefs",
            }
            data2_gg = {
                "event_id": "c491f05b066449d95732c4f52ac57e66",
                "player_choice": "Las Vegas Raiders",
            }

            # List of asynchronous tasks
            tasks = []
            for round in init_rounds:
                match = round.match
                user_1 = round.player_1.player
                user_2 = round.player_2.player

                # Concurrently update matches with data
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

                # Asynchronous game updates
                tasks.extend([
                    asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                    asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                    asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                    asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
                ])

            # Run all tasks asynchronously
            await asyncio.gather(*tasks)

        # Asynchronous update of test 2 events
        async def async_update_test_2_events(self):
            update_path_1 = os.path.join(
                self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-3.json'
            )
            update_path_2 = os.path.join(
                self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-3.json'
            )
            update_path_3 = os.path.join(
                self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy4-1.json'
            )
            update_path_4 = os.path.join(
                self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy3-1.json'
            )

            # Asynchronous tasks for event updates
            tasks = [
                asyncio.to_thread(self.support.test_get_nfl_events, update_path_1),
                asyncio.to_thread(self.support.update_golden_game, update_path_2, "c1b7e562062eb3bac053a2f5ecf399f9"),
                asyncio.to_thread(self.support.update_golden_game, update_path_3, "c1b7e562062eb3bac053a2f5ecf399f9"),
                asyncio.to_thread(self.support.test_get_nfl_events, update_path_4),
            ]

            # Run all tasks concurrently
            await asyncio.gather(*tasks)

        # Asynchronous print function for the second round
        async def async_print_second_round(self):
            tournament = self.tournament_record
            init_rounds = await asyncio.to_thread(
                Round.objects.get_tourney_level_rounds,
                tournament=tournament,
                level=tournament.levels - 2,
            )

            # Asynchronous loop to print round information
            for round in init_rounds:
                print(f"Match winner: {round.match.winner}, Round winner: {round.winner.player}")
    #  --- Second Round Event Uploads---

    #  --- Third Round Event Uploads---
    async def async_simulate_third_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 3,
        )

        # Data for match updates
        data1 = {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Miami Dolphins",
        }
        data2 = {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Baltimore Ravens",
        }
        data1_gg = {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Los Angeles Chargers",
        }
        data2_gg = {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Minnesota Vikings",
        }

        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Asynchronous match updates
            for _ in range(5):
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

            # Asynchronous game updates
            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    # Asynchronous update for test 3 events
    async def async_update_test_3_events(self):
        update_path_1 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-4.json'
        )
        update_path_2 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-4.json'
        )
        update_path_3 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy5-1.json'
        )
        update_path_4 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy4-1.json'
        )

        # Async test event updates
        tasks = [
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_1),
            asyncio.to_thread(self.support.update_golden_game, update_path_2, "76ae384526017414d68d617bf80b8aab"),
            asyncio.to_thread(self.support.update_golden_game, update_path_3, "76ae384526017414d68d617bf80b8aab"),
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_4),
        ]

        # Run all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous print for the third round
    async def async_print_third_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 3,
        )

        # Asynchronous loop to print round information
        for round in init_rounds:
            print(f"Match winner: {round.match.winner}, Round winner: {round.winner.player}")
    #  --- Third Round Event Uploads---

    #  --- Forth Round Event Uploads---
    async def async_simulate_fourth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 4,
        )

        data1 = {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Dallas Cowboys",
        }
        data2 = {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Seattle Seahawks",
        }
        data1_gg = {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Pittsburgh Steelers",
        }
        data2_gg = {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Arizona Cardinals",
        }

        # List of asynchronous tasks for updating matches
        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Asynchronous match updates
            for _ in range(5):
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

            # Asynchronous game updates
            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    # Asynchronous update for test 4 events
    async def async_update_test_4_events(self):
        update_path_1 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-5.json'
        )
        update_path_2 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-5.json'
        )
        update_path_3 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy6-1.json'
        )
        update_path_4 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy5-1.json'
        )

        # Asynchronous tasks for test updates
        tasks = [
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_1),
            asyncio.to_thread(self.support.update_golden_game, update_path_2, "41c4d77b6a910a6b2364fbeb51dba059"),
            asyncio.to_thread(self.support.update_golden_game, update_path_3, "41c4d77b6a910a6b2364fbeb51dba059"),
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_4),
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    # Asynchronous print function for the fourth round
    async def async_print_fourth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 4,
        )

        for round in init_rounds:
            print(f"Match winner: {round.match.winner}, Round winner: {round.winner.player}")
    #  --- Fourth Round Event Uploads---

    #  --- Fifth Round Event Uploads---
    async def async_simulate_fifth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 5,
        )

        data1 = {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "New York Jets",
        }
        data2 = {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "Atlanta Falcons",
        }
        data1_gg = {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "New Orleans Saints",
        }
        data2_gg = {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "Detroit Lions",
        }

        # List of asynchronous tasks
        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Asynchronous match updates
            for _ in range(5):
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

            # Asynchronous game updates
            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        # Execute all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous update for test 5 events
    async def async_update_test_5_events(self):
        update_path_1 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-6.json'
        )
        update_path_2 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-6.json'
        )
        update_path_3 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy7-1.json'
        )
        update_path_4 = os.path.join(
            self.base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy6-1.json'
        )

        # List of asynchronous tasks for updates
        tasks = [
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_1),
            asyncio.to_thread(self.support.update_golden_game, update_path_2, "5e0c5b79c3cb142f3361ade464174b68"),
            asyncio.to_thread(self.support.update_golden_game, update_path_3, "5e0c5b79c3cb142f3361ade464174b68"),
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_4),
        ]

        # Run all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous print function for the fifth round
    async def async_print_fifth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 5,
        )

        for round in init_rounds:
            print(f"Match winner: {round.match.winner}, Round winner: {round.winner.player}")
    #  --- Fifth Round Event Uploads---

    #  --- Sixth Round Event Uploads---
    async def async_simulate_sixth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 6,
        )

        data1 = {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Tennessee Titans",
        }
        data2 = {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Indianapolis Colts",
        }
        data1_gg = {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Washington Commanders",
        }
        data2_gg = {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Miami Dolphins",
        }

        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Asynchronous match updates
            for _ in range(5):
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

            # Asynchronous game updates
            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        # Run all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous update of test 6 events
    async def async_update_test_6_events(self):
        base_test_path = self.base_test_path
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-7.json')
        update_path_2 = os.path.join(base_test_path, 'test_files/tourney-json/initial_events/tourney-nfl-copy1-7.json')
        update_path_3 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy8-1.json')
        update_path_4 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy7-1.json')

        # Asynchronous tasks for test updates
        tasks = [
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_1),
            asyncio.to_thread(self.support.update_golden_game, update_path_2, "ad1bbe3e94716ca03c3059092cbd1eee"),
            asyncio.to_thread(self.support.update_golden_game, update_path_3, "ad1bbe3e94716ca03c3059092cbd1eee"),
            asyncio.to_thread(self.support.test_get_nfl_events, update_path_4),
        ]

        # Run all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous print function for the sixth round
    async def async_print_sixth_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 6,
        )

        for round in init_rounds:
            print(f'match winner: {round.match.winner}, round winner: {round.winner.player}')
    #  --- Sixth Round Event Uploads---

    #  --- Sixth Round Event Uploads---
    async def async_simulate_seventh_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 7,
        )

        data1 = {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Houston Texans",
        }
        data2 = {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Denver Broncos",
        }
        data1_gg = {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "New England Patriots",
        }
        data2_gg = {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "Los Angeles Chargers",
        }

        # List of asynchronous tasks for match updates
        tasks = []
        for round in init_rounds:
            match = round.match
            user_1 = round.player_1.player
            user_2 = round.player_2.player

            # Asynchronous match updates
            for _ in range(5):
                tasks.append(self.async_update_match(match, data1, user_1))
                tasks.append(self.async_update_match(match, data2, user_2))

            # Asynchronous game updates
            tasks.extend([
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_1.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_2.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_3.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_4.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_1_game_5.id, user_2, data2),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_1.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_2.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_3.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_4.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.player_2_game_5.id, user_1, data1),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_1, data1_gg),
                asyncio.to_thread(Game.objects.update_by_id, match.golden_game.id, user_2, data2_gg),
            ])

        # Run all tasks asynchronously
        await asyncio.gather(*tasks)

    # Asynchronous update of test 7 events
    async def async_update_test_7_events(self):
        base_test_path = self.base_test_path
        update_path_1 = os.path.join(base_test_path, 'test_files/tourney-json/update_events/tourney-nfl-copy8-1.json')

        # Async task for event update
        await asyncio.to_thread(self.support.test_get_nfl_events, update_path_1)

    # Asynchronous print function for the seventh round
    async def async_print_seventh_round(self):
        tournament = self.tournament_record
        init_rounds = await asyncio.to_thread(
            Round.objects.get_tourney_level_rounds,
            tournament=tournament,
            level=tournament.levels - 7,
        )

        for round in init_rounds:
<<<<<<< Updated upstream
            print(f'Round level = {round.level_num}')
            print(RoundSerializer(round).data)
            print(MatchSerializer(round.match).data)
            print(f'match winner: {round.match.winner}, round winner: {round.winner}')
=======
            # print(f'Round level = {round.level_num}')
            # print(RoundSerializer(round).data)
            # print(MatchSerializer(round.match).data)
            print( f'match winner:{round.match.winner}, round winner: {round.winner} ')
            # print(f'match winner:{round.match.winner}, round winner: {round.winner.player} ')


>>>>>>> Stashed changes
    #  --- Seventh Round Event Uploads---


    # run rounds



    # run rounds

    async def async_run_round_one(self):
        await asyncio.sleep(1)
        await self.async_simulate_first_round()
        await asyncio.sleep(1)
        await self.async_update_test_events()
        # Optional printing step
        # await asyncio.sleep(1)
        # await self.async_print_init_round()

<<<<<<< Updated upstream
    # Run second round
    async def async_run_round_two(self):
        await asyncio.sleep(1)
        await self.async_simulate_second_round()
        await asyncio.sleep(1)
        await self.async_update_test_2_events()
        if self.tournament_record.levels == 2:
            await asyncio.sleep(1)
            await self.async_print_second_round()
        else:
            print("Second Round Finished")

    # Run third round
    async def async_run_round_three(self):
        await asyncio.sleep(1)
        await self.async_simulate_third_round()
        await asyncio.sleep(1)
        await self.async_update_test_3_events()
        if self.tournament_record.levels == 3:
            await asyncio.sleep(1)
            await self.async_print_third_round()
        else:
            print("Third Round Finished")

    # Run fourth round
    async def async_run_round_four(self):
        await asyncio.sleep(1)
        await self.async_simulate_fourth_round()
        await asyncio.sleep(1)
        await self.async_update_test_4_events()
        if self.tournament_record.levels == 4:
            await asyncio.sleep(1)
            await self.async_print_fourth_round()
        else:
            print("Fourth Round Finished")

    # Run fifth round
    async def async_run_round_five(self):
        await asyncio.sleep(1)
        await self.async_simulate_fifth_round()
        await asyncio.sleep(1)
        await self.async_update_test_5_events()
        if self.tournament_record.levels == 5:
            await asyncio.sleep(1)
            await self.async_print_fifth_round()
        else:
            print("Fifth Round Finished")

    # Run sixth round
    async def async_run_round_six(self):
        await asyncio.sleep(1)
        await self.async_simulate_sixth_round()
        await asyncio.sleep(1)
        await self.async_update_test_6_events()
        if self.tournament_record.levels == 6:
            await asyncio.sleep(1)
            await self.async_print_sixth_round()
        else:
            print("Sixth Round Finished")

    # Run seventh round
    async def async_run_round_seven(self):
        await asyncio.sleep(1)
        await self.async_simulate_seventh_round()
        await asyncio.sleep(1)
        await self.async_update_test_7_events()
        if self.tournament_record.levels == 7:
            await asyncio.sleep(1)
            await self.async_print_seventh_round()
        else:
            print("Seventh Round Finished")
=======
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
        time.sleep(3)
        self.Simulate_Third_Round()
        time.sleep(3)
        self.update_test_3_events()
        # if self.tournament_record.levels == 3:
        #     time.sleep(1)
        #     self.print_third_round()
        # else:
        #     print(f'Third Round Finished')

    def run_round_four(self):
        time.sleep(4)
        self.Simulate_Fourth_Round()
        time.sleep(4)
        self.update_test_4_events()
        # if self.tournament_record.levels == 4:
        #     time.sleep(1)
        #     self.print_fourth_round()
        # else:
        #     print(f'Forth Round Finished')
    def run_round_five(self):
        time.sleep(6)
        self.Simulate_Fifth_Round()
        time.sleep(6)
        self.update_test_5_events()
        # if self.tournament_record.levels == 5:
        #     time.sleep(1)
        #     self.print_fifth_round()
        # else:
        #     print(f'Fifth Round Finished')


    def run_round_six(self):
        time.sleep(10)
        self.Simulate_Sixth_Round()
        time.sleep(10)
        self.update_test_6_events()
        # if self.tournament_record.levels == 6:
        #     time.sleep(1)
        #     self.print_sixth_round()
        # else:
        #     print(f'Sixth Round Finished')

    def run_round_seven(self):
        time.sleep(16)
        self.Simulate_Seventh_Round()
        time.sleep(16)
        self.update_test_7_events()
        # if self.tournament_record.levels == 7:
        #     time.sleep(1)
        #     self.print_seventh_round()
>>>>>>> Stashed changes

    # Asynchronous test run
    async def run_test(self):
        logging.info("Starting -Tournament Unit test 1 Tourney Simulator 1 Test")
        await self.test_setup()
        logging.info("Finished Setup")
        await asyncio.sleep(1)
        await self.make_tournament()
        logging.info("Finished Making Tourney")

        await self.async_run_round_one()
        logging.info("Finished Round 1")

<<<<<<< Updated upstream
=======
    #  --- Run Test---

    def run_test(self):
        # print("starting test")
        self.test_setup()
        time.sleep(1)
        # print("Making Tourney")
        self.make_tournament()
        # print("Starting Rounds")
        self.run_round_one()
>>>>>>> Stashed changes
        if self.tournament_record.levels >= 2:
            await self.async_run_round_two()
            logging.info("Finished Round 2")

        if self.tournament_record.levels >= 3:
            await self.async_run_round_three()
            logging.info("Finished Round 3")

        if self.tournament_record.levels >= 4:
            await self.async_run_round_four()
            logging.info("Finished Round 4")

        if self.tournament_record.levels >= 5:
            await self.async_run_round_five()
            logging.info("Finished Round 5")

        if self.tournament_record.levels >= 6:
            await self.async_run_round_six()
            logging.info("Finished Round 6")

        if self.tournament_record.levels >= 7:
            await self.async_run_round_seven()
            logging.info("Finished Round 7")

        logging.info("Finished -Tournament Unit test 1 Tourney Simulator 1 Test")