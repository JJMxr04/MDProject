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
from core.event.serializers.event import EventSerializer, TeamScoreSerializer
from core.game.serializers.game import GameSerializer
from core.event.models.event import Event
from core.event.models.sport import Sport
from core.game.models import Game
from core.user.models import User
from core.user.serializers import UserSerializer
sport_model = Sport()
from core.event.crons.sportUpdate import SportCron
sport_cron = SportCron()

from core.event.crons.eventUpdate import EventCron
event_cron = EventCron()


class Support:
    def read_list_from_file(self,file_path):
        try:
            with open(file_path, 'r') as file:
                # Read lines from the file and remove newline characters
                file_content = [line.strip() for line in file.readlines()]

            print(f"List read from '{file_path}': {file_content}")
            return file_content
        except FileNotFoundError:
            print(f"File '{file_path}' not found.")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    def read_file_and_save_as_list(self,input_file, output_file):
        try:
            with open(input_file, 'r') as file:
                # Read lines from the file and remove newline characters
                file_content = [line.strip() for line in file.readlines()]

            # Save the content as a list in another file
            with open(output_file, 'w') as output:
                for item in file_content:
                    output.write(f"{item}\n")

            print(f"Content of '{input_file}' saved as a list in '{output_file}'.")
        except FileNotFoundError:
            print(f"File '{input_file}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def process_files_in_folder(self,folder_path, output_file):
        try:
            # Get a list of all files in the folder
            file_list = [file for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]

            # Save the list to the output text file
            with open(output_file, 'w') as output_file:
                for file_name in file_list:
                    output_file.write(f"{file_name}\n")

            print(f"List of files saved to '{output_file.name}'")
        except FileNotFoundError:
            print(f"Folder '{folder_path}' not found.")
        except Exception as e:
            print(f"An error occurred: {e}")

    def write_json_to_file(self,data, filename):
        """
        Write JSON data to a file in a formatted way.

        Parameters:
        - data: The data to be written.
        - filename: The name of the file to write to.
        """
        json_data = serialize('json', data, indent=2)
        with open(filename, 'a') as file:
            file.write(json_data)

    def read_json_file(self,file_path):
        try:
            with open(file_path, 'r') as file:
                json_data = file.read()
                if json_data.strip():
                    return json_data
                else:
                    return None
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            return None

    def test_get_nfl_events(self,file):
        api_data = support.read_json_file(file)
        if api_data is None:
            return False

        api_data_json = json.loads(api_data)

        for event in api_data_json:
            event['id'] = uuid.UUID(event['id'])
            event_schema = EventSerializer(data=event)
            if event_schema.is_valid():

                data = event_schema.validated_data
                data['id'] = event['id']
                if (data.get('away_team')) is None or (data.get('away_team') is None):
                    continue
                try:
                    existing_event = Event.objects.get(id=data.get("id"))
                except ObjectDoesNotExist:
                    event_game = Event(**data)
                    event_game.save()
                    continue

                if data.get('completed'):
                    team_schema = TeamScoreSerializer(data=event['scores'][0])
                    if team_schema.is_valid():
                        score1 = team_schema.validated_data
                    team_schema = team_schema = TeamScoreSerializer(data=event['scores'][1])
                    if team_schema.is_valid():
                        score2 = team_schema.validated_data
                    Event.objects.get_event_state(data['id'], data['completed'], data['scores'], score1,score2)


        return Response("Success", status=status.HTTP_200_OK)

    def get_test_players(self):

        owner = User.objects.get_object_by_email("test1@test.com")
        if owner== Http404:
            user_1_data = {
                "username": "test1",
                "first_name": "test1",
                "last_name": "test1",
                "password": "password",
                "email": "test1@test.com"
            }
            serializer = UserSerializer(data=user_1_data)
            serializer.is_valid(raise_exception=True)
            owner = User.objects.create_user_ex(user_1_data['username'],user_1_data['first_name'],user_1_data['last_name'], user_1_data['email'],user_1_data['password'], )

        player_2 = User.objects.get_object_by_email("test2@test.com")
        if player_2 == Http404:
            user_2_data = {
                "username": "test2",
                "first_name": "test2",
                "last_name": "test2",
                "password": "password",
                "email": "test2@test.com"
            }
            serializer = UserSerializer(data=user_2_data)

            serializer.is_valid(raise_exception=True)
            serializer.validated_data
            player_2 = User.objects.create_user_ex(user_2_data['username'],user_2_data['first_name'],user_2_data['last_name'],user_2_data['email'],user_2_data['password'],)
        owner = User.objects.get_object_by_email("test1@test.com")
        player_2 = User.objects.get_object_by_email("test2@test.com")
        # print(owner, player_2)
        return owner, player_2

    def flush_database(self):
        call_command('flush', interactive=False)

support = Support()

class Test1:

    def test1(self):
        print("Starting Event Creation Testing 1")
        Support.test_get_nfl_events('testfiles/nfl-copy1.json')
        # Needs to add checks
        print("Stopped Event Creation Testing 1")

    def test2(self):
        print("Starting SportCronTesting 2")
        sport_cron.get_sports()
        print(sport_cron.get_active_sports())
        # Needs to add checks
        print("Stopped SportCronTesting 2")

    def test3(self):
        print("Starting EventCronTesting 3")
        events = event_cron.get_sport_events("americanfootball_nfl.json")
        pretty = json.dumps(events)
        print(pretty)
        # Needs to add checks
        print("Stopped EventCronTesting 3")

    def test4(self):
        print("Starting EventCronTesting 4")
        events = event_cron.update_all_events()
        print(events)
        # Needs to add checks
        print("Stopped EventCronTesting 4")

    def test5(self):
        print("Starting Event Creation Testing 5")
        sport_cron.get_sports()
        sports = sport_cron.get_active_sports()
        # print(sports)
        # event_cron.get_sport_events("soccer_switzerland_superleague")
        # print(sports)
        for sport in sports:
            Support.test_get_nfl_events(f'testfiles/originals/{sport}.json')
        # Needs to add checks
        print("Stopped Event Creation Testing 5")

    def test5_5(self):
        print("Starting sport Creation Testing 5.5")

        folder_path = 'testfiles/originals'
        output_file = 'testfiles/sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = Support.read_list_from_file(output_file)
        print(sports)
        # sport_cron.get_sports()
        # sports = sport_cron.get_active_sports()
        # # print(sports)
        # # event_cron.get_sport_events("soccer_switzerland_superleague")
        # # print(sports)
        for sport in sports:
            support.test_get_nfl_events(f'testfiles/originals/{sport}')
        # Needs to add checks
        print("Stopped sport Creation Testing 5.5")

    def test6(self):
        print("Starting Game Creation and Update Testing 6")
        owner, player_2 = Support.get_test_players()
        game = Game.objects.create_game(owner,player_2)
        data1 = {
            "event_id": "85ccca87e453d00340982559fd50c443",
            "player_choice": "Penn State Nittany Lions"
        }
        data2 = {
            "event_id": "85ccca87e453d00340982559fd50c443",
            "player_choice": "Ole Miss Rebels"
        }
        Game.objects.update_by_id(game.id,owner,data1)
        Game.objects.update_by_id(game.id, player_2, data2)
        game1 = Game.objects.get_object_by_id(game.id)
        print(game1.event)
        print(game1.owner_choice)
        print(game1.player_2_choice)
        # Needs to add checks

        print("Stopped Game Creation and Update Testing 6")

    def test7(self):
        print("Starting Game Creation and Signal Update Testing 7")
        support.flush_database()
        folder_path = 'originals'
        output_file = 'sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'nfl-copy1-1.json')
        owner, player_2 = support.get_test_players()

        game = Game.objects.create_game(owner, player_2)

        data1 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        }
        data2 = {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        }

        Game.objects.update_by_id(game.id, owner, data1)
        Game.objects.update_by_id(game.id, player_2, data2)
        support.test_get_nfl_events(f'nfl-copy2-1.json')
        game1 = Game.objects.get_object_by_id(game.id)
        if game1.event.winner == "Miami Dolphins":
            print(f"Event winner:{game1.event.winner} - pass")
        else:
            print(f"Event winner:{game1.event.winner} - fail")
        if game1.owner_choice == "Miami Dolphins":
            print(f"Owner Choice:{game1.owner_choice} - pass")
        else:
            print(f"Owner Choice:{game1.owner_choice} - fail")
        if game1.player_2_choice == "Tennessee Titans":
            print(f"Player_2 Choice:{game1.player_2_choice} - pass")
        else:
            print(f"Player_2 Choice:{game1.play_2_choice} - fail")
        if game1.winner == "Miami Dolphins":
            print(f"Game winner:{game1.winner} - pass")
        else:
            print(f"Game winner:{game1.winner} - fail")
        print("Stopped Game Creation and Signal Update Testing 7")

    def test8(self,amount):
        print(f"Starting Test  8- testing {amount} games being made and updated")
        support.flush_database()
        print("Test 8 - first update - Start")
        folder_path = 'originals'
        output_file = 'sports_list.txt'
        support.process_files_in_folder(folder_path, output_file)
        sports = support.read_list_from_file(output_file)
        support.test_get_nfl_events(f'nfl-copy1-1.json')
        print("Test 8 - first update - Finish")
        print("Test 8 Starting Game creating for loop")
        for x in range(1,amount):
            # print(x)
            owner, player_2 = support.get_test_players()

            game = Game.objects.create_game(owner, player_2)

            data1 = {
                "event_id": "484bc5582bb44ab79a1e942cf8762eda",
                "player_choice": "Miami Dolphins"
            }
            data2 = {
                "event_id": "484bc5582bb44ab79a1e942cf8762eda",
                "player_choice": "Tennessee Titans"
            }

            Game.objects.update_by_id(game.id, owner, data1)
            Game.objects.update_by_id(game.id, player_2, data2)
        print("Test 8 - Second update - Start")
        support.test_get_nfl_events(f'nfl-copy2-1.json')
        print("Test 8 - Second update - Finish")
        print("Finish Test  8- testing 1000000 games being made and updated")


