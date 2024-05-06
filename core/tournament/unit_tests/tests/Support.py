import os
from django import setup
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize
import uuid
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command
from django.http import Http404
import json

# Importing various serializers and models from different Django apps
from core.event.serializers.event import EventSerializer, TeamScoreSerializer
from core.game.serializers.game import GameSerializer
from core.event.models.event import Event
from core.event.models.sport import Sport
from core.game.models import Game
from core.user.models import User
from core.match.models import Match
from core.user.serializers import UserSerializer

# Instantiating Sport model
sport_model = Sport()

# Importing cron jobs for scheduled tasks
from core.event.crons.sportUpdate import SportCron
sport_cron = SportCron()

from core.event.crons.eventUpdate import EventCron
from core.event.crons.teamUpdate import TeamCron
from core.event.serializers.team import TeamSerializer
from core.event.serializers.sport import SportSerializer
from core.event.models import Team
event_cron = EventCron()
team_cron = TeamCron()

# Importing datetime to manipulate date and time
from datetime import datetime, timedelta

from io import StringIO
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings

# Class containing various utility functions
class Support:
    databases = ['default', 'test_mirror']

    def updateSports(self):
        sport_cron.get_sports()
    def get_date_for_week_from_now(self):
        """
        Returns the date for a week from now.
        """
        current_date = datetime.now().date()
        week_from_now = current_date + timedelta(weeks=1)  # Add a week to current date
        return week_from_now

    def read_list_from_file(self, file_path):
        """
        Reads a file line-by-line, stripping newline characters, and returns the lines as a list.
        Handles file not found and other exceptions.
        """
        try:
            with open(file_path, 'r') as file:
                # Read and remove newline characters
                file_content = [line.strip() for line in file.readlines()]
            return file_content
        except FileNotFoundError:
            print(f"File '{file_path}' not found.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def read_file_and_save_as_list(self, input_file, output_file):
        """
        Reads from input file, and saves each line into output file as a list of strings.
        """
        try:
            with open(input_file, 'r') as file:
                # Read lines and remove newline characters
                file_content = [line.strip() for line in file.readlines()]

            # Write to output file
            with open(output_file, 'w') as output:
                for item in file_content:
                    output.write(f"{item}\n")
        except FileNotFoundError:
            print(f"File '{input_file}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def process_files_in_folder(self, folder_path, output_file):
        """
        Lists all files in a given folder and writes the filenames to an output text file.
        """
        try:
            # Get list of files in the folder
            file_list = [file for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]

            # Save list of filenames
            with open(output_file, 'w') as output:
                for file_name in file_list:
                    output.write(f"{file_name}\n")
        except FileNotFoundError:
            print(f"Folder '{folder_path}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def write_json_to_file(self, data, filename):
        """
        Write JSON data to a file in a formatted way.
        """
        json_data = serialize('json', data, indent=2)  # Convert data to JSON
        with open(filename, 'a') as file:
            file.write(json_data)

    def read_json_file(self, file_path):
        """
        Reads a JSON file and returns its content as a string.
        Handles file not found and other exceptions.
        """
        try:
            with open(file_path, 'r') as file:
                json_data = file.read()
                if json_data.strip():  # If the file has content
                    return json_data
                else:  # If the file is empty
                    return None
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            return None

    def test_get_nfl_events(self, file):
        # print(SportSerializer(Sport.objects.get_by_key("americanfootball_nfl")).data)
        """
        Reads a JSON file, loads events, and updates Event objects.
        Creates or updates Event objects with appropriate data.
        """
        # Read the file content
        api_data = self.read_json_file(file)
        # print(Sport.objects.filter())
        # print(api_data)
        if api_data is None:  # If the file is empty or not found
            return False
        api_data_json = json.loads(api_data)
        # Get the "americanfootball_nfl" sport object
        sport = Sport.objects.get_by_key("americanfootball_nfl")
        # print(sport)
        # print(SportSerializer(Sport.objects.get_by_key("americanfootball_nfl")).data)
        for event in api_data_json:
            if event.get("away_team") is None or event.get("home_team") is None:
                # Skip if away_team or home_team is missing
                continue

            event['id'] = uuid.UUID(event['id'])  # Convert ID to UUID
            event['title'] = sport.title  # Set sport details
            event['group'] = sport.group
            event['description'] = sport.description

            # Set the IDs for home and away teams using the TeamSerializer
            event['home_team_team'] = TeamSerializer(team_cron.check_team(event.get('home_team'), sport.title, sport.group)).data['id']
            event['away_team_team'] = TeamSerializer(team_cron.check_team(event.get('away_team'), sport.title, sport.group)).data['id']

            # Validate event schema
            event_schema = EventSerializer(data=event)

            if event_schema.is_valid():
                data = event_schema.validated_data
                data['id'] = event['id']

                # Check if home and away teams are still valid
                if data.get("away_team") is None or data.get("home_team") is None:
                    continue

                try:
                    existing_event = Event.objects.get(id=data.get("id"))
                    if existing_event.completed != data['completed']:
                        # If completed status changed, update the event
                        team_schema = TeamScoreSerializer(data=event['scores'][0])
                        if team_schema.is_valid():
                            score1 = team_schema.validated_data

                        team_schema = TeamScoreSerializer(data=event['scores'][1])
                        if team_schema.is_valid():
                            score2 = team_schema.validated_data

                        Event.objects.get_event_state(
                            data['id'],
                            data['completed'],
                            data['scores'],
                            score1,
                            score2
                        )
                except ObjectDoesNotExist:
                    # If event does not exist, create a new one
                    event_game = Event(**data)
                    event_game.save()

    def get_test_players(self):
        """
        Ensures test users are created and returns two test users.
        Creates new users if they don't exist.
        """
        # Attempt to get a test user by email
        owner = User.objects.get_object_by_email("test1@test.com")
        if owner == Http404:
            # If user doesn't exist, create a new user
            user_1_data = {
                "username": "test1",
                "first_name": "test1",
                "last_name": "test1",
                "password": "password",
                "email": "test1@test.com"
            }
            serializer = UserSerializer(data=user_1_data)
            serializer.is_valid(raise_exception=True)  # Validate the data
            owner = User.objects.create_user_ex(
                user_1_data['username'],
                user_1_data['first_name'],
                user_1_data['last_name'],
                user_1_data['email'],
                user_1_data['password']
            )

        player_2 = User.objects.get_object_by_email("test2@test.com")
        if player_2 == Http404:
            # If user doesn't exist, create another user
            user_2_data = {
                "username": "test2",
                "first_name": "test2",
                "last_name": "test2",
                "password": "password",
                "email": "test2@test.com"
            }
            serializer = UserSerializer(data=user_2_data)
            serializer.is_valid(raise_exception=True)  # Validate the data
            player_2 = User.objects.create_user_ex(
                user_2_data['username'],
                user_2_data['first_name'],
                user_2_data['last_name'],
                user_2_data['email'],
                user_2_data['password']
            )

        return owner, player_2  # Return the test users

    def flush_database(self):
        """
        Flushes the database, excluding specific core models.
        """
        # Clear most data but preserve data from specific models
        call_command('flush_except', 'core_event_team', 'core_sport','core_user_user')

    def datadump(self):
        """
        Dumps data from specific models to a serialized format.
        """
        # Redirect output to a StringIO to suppress output during command execution
        null_output = StringIO()

        # Dump data without printing to console
        call_command('dumpdata', 'core_event.Team', exclude=['contenttypes', 'auth.Permission'], indent=2,
                     stdout=null_output)
        call_command('dumpdata', 'core_event.Sport', exclude=['contenttypes', 'auth.Permission'], indent=2,
                     stdout=null_output)

        # You can still get the serialized data if you need it
        dumped_data = null_output.getvalue()

    def load_data_sport_team(self):
        """
        Loads data from serialized JSON files into Django tables if the tables are empty.
        """
        # Check if the Sport and Team tables are empty
        if Sport.objects.exists():
            print("Sport table is not empty. Data load skipped.")
            return
        if Team.objects.exists():
            print("Team table is not empty. Data load skipped.")
            return

        # Determine the file paths
        current_file_path = __file__
        current_file_directory = os.path.dirname(current_file_path)

        # Define the base path relative to the test directory
        base_test_path = os.path.abspath(current_file_directory)
        fixtures_dir = os.path.join(settings.BASE_DIR, 'core_event', 'fixtures')
        sport_data_file = os.path.join(base_test_path, 'test_files/table_dumps/dataSport.json')
        team_data_file = os.path.join(base_test_path, 'test_files/table_dumps/dataTeam.json')

        # Ensure the files exist before attempting to load them
        if not os.path.exists(sport_data_file):
            raise ImproperlyConfigured(f"{sport_data_file} does not exist.")
        if not os.path.exists(team_data_file):
            raise ImproperlyConfigured(f"{team_data_file} does not exist.")

        # Load the data from the JSON files into the respective tables
        call_command('loaddata', sport_data_file)  # Loads data into core_sport
        call_command('loaddata', team_data_file)  # Loads data into core_event_team

        print("Data loaded successfully from dataSport.json and dataTeam.json")

    def update_golden_game(self, json_file_path, target_id):
        """
        Updates a specific object in a JSON file based on a target ID.
        """
        try:
            # Read the JSON file
            with open(json_file_path, 'r') as file:
                data = json.load(file)

            # Iterate through objects to find the one with the target ID
            for obj in data:
                if obj.get("id") == target_id:
                    # Update commence time to 6 days from now
                    current_time = datetime.now()
                    new_commence_time = current_time + timedelta(days=6)
                    new_commence_time_str = new_commence_time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    obj["commence_time"] = new_commence_time_str
                    break  # Stop loop after updating

            # Write updated data back to the file
            with open(json_file_path, 'w') as file:
                json.dump(data, file, indent=2)

            return obj  # Return the updated object

        except FileNotFoundError:
            print(f"File not found: {json_file_path}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None

    def endEvents(self):
        """
        Marks all events that have passed as completed.
        """
        events = Event.objects.filter(completed=False)
        x = 0
        for event in events:
            current_time = datetime.now()  # Current time
            eventTime = datetime.strptime(event.commence_time, "%Y-%m-%dT%H:%M:%SZ")
            if current_time > eventTime:  # If event is in the past
                event.completed = True
                event.save()  # Mark as completed
                x += 1
                print(f"Completed {x} event(s)")

    def deleteExtraTeams(self):
        """
        Deletes duplicate teams based on team name.
        """
        teams = Team.objects.all()  # Get all teams
        for team in teams:
            name = team.team_name

            teams_with_same_name = Team.objects.filter(team_name=name)
            if len(teams_with_same_name) > 1:
                # If there are duplicates, delete the extras
                print(f"{name} has {len(teams_with_same_name)} duplicates")
                teams_with_same_name[1].delete()

    def checkExtraTeams(self):
        """
        Checks for duplicate teams and logs them.
        """
        teams = Team.objects.all()  # Get all teams
        for team in teams:
            name = team.team_name

            teams_with_same_name = Team.objects.filter(team_name=name)
            if len(teams_with_same_name) > 1:
                # If there are duplicates, log the count
                print(f"{name} has {len(teams_with_same_name)} duplicates")