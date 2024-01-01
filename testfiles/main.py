# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize
import uuid
from rest_framework.response import Response
from rest_framework import status



# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()

# Other imports
import json
from core.event.serializers.event import EventSerializer, TeamScoreSerializer
from core.game.serializers.game import GameSerializer
from core.event.models.event import Event
from core.event.models.sport import Sport
from core.game.models import Game
from core.user.models import User
sport_model = Sport()
from core.event.crons.sportUpdate import SportCron
sport_cron = SportCron()

from core.event.crons.eventUpdate import EventCron
event_cron = EventCron()


def read_list_from_file(file_path):
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

def read_file_and_save_as_list(input_file, output_file):
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


def process_files_in_folder(folder_path, output_file):
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

def write_json_to_file(data, filename):
    """
    Write JSON data to a file in a formatted way.

    Parameters:
    - data: The data to be written.
    - filename: The name of the file to write to.
    """
    json_data = serialize('json', data, indent=2)
    with open(filename, 'a') as file:
        file.write(json_data)

def read_json_file(file_path):
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


def test_get_nfl_events(file):
    api_data = read_json_file(file)
    if api_data is None:
        return False
    # if file == "testfiles/originals/soccer_switzerland_superleague.json":
    #     print(api_data)
    api_data_json = json.loads(api_data)
    print(api_data_json)
    for event in api_data_json:
        # if file == "testfiles/originals/soccer_switzerland_superleague.json":
        #     print(f"Event: {event}")
        # print(1)
        event['id'] = uuid.UUID(event['id'])
        # print(event['id'])
        event_schema = EventSerializer(data=event)
        if event_schema.is_valid():
            data = event_schema.validated_data
            data['id'] = event['id']
            print(f"{data.get('id')}:{event['id']}")
            if (data.get('away_team')) is None or (data.get('away_team') is None):
                continue
            try:
                print(4)
                existing_event = Event.objects.get(id=data.get("id"))
            except ObjectDoesNotExist:
                print(5)
                event_game = Event(**data)
                event_game.save()
                continue

            if data.get('completed'):
                team_schema = TeamScoreSerializer(data=json.loads(event['scores'])[0])
                if team_schema.is_valid():
                    score1 = team_schema.validated_data
                team_schema = TeamScoreSerializer(data=json.loads(event['scores'])[1])
                if team_schema.is_valid():
                    score2 = team_schema.validated_data

                # Assuming get_sport_state is a method of your Event model
                existing_event.get_sport_state(data.get('completed'), score1, score2)

    return Response("Success", status=status.HTTP_200_OK)


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    # print("Starting Event Creation Testing 1")
    # test_get_nfl_events('testfiles/nfl-copy1.json')
    # print("Stopped Event Creation Testing 1")

    # print("Starting SportCronTesting 2")
    # sport_cron.get_sports()
    # print(sport_cron.get_active_sports())
    # print("Stopped SportCronTesting 2")
    # "americanfootball_nfl.json"

    # print("Starting EventCronTesting 3")
    # # events = event_cron.get_sport_events("americanfootball_nfl.json")
    # # pretty = json.dumps(events)
    # print(events)
    # print("Stopped EventCronTesting 3")

    # print("Starting EventCronTesting 4")
    # events = event_cron.update_all_events()
    # # print(events)
    # print("Stopped EventCronTesting 4")

    # print("Starting Event Creation Testing 5")
    #
    # sport_cron.get_sports()
    # sports = sport_cron.get_active_sports()
    # # print(sports)
    # # event_cron.get_sport_events("soccer_switzerland_superleague")
    # # print(sports)
    # for sport in sports:
    #     test_get_nfl_events(f'testfiles/originals/{sport}.json')
    # print("Stopped Event Creation Testing 5")

    # print("Starting sport Creation Testing 5.5")
    #
    # folder_path = 'testfiles/originals'
    # output_file = 'testfiles/sports_list.txt'
    #
    #
    #
    # process_files_in_folder(folder_path, output_file)
    #
    # sports = read_list_from_file(output_file)
    # print(sports)
    # # sport_cron.get_sports()
    # # sports = sport_cron.get_active_sports()
    # # # print(sports)
    # # # event_cron.get_sport_events("soccer_switzerland_superleague")
    # # # print(sports)
    # for sport in sports:
    #     test_get_nfl_events(f'testfiles/originals/{sport}')
    # print("Stopped sport Creation Testing 5.5")

    # IDs
    # 51387afd-c3f3-4750-83fd-db3ff20048b3
    # acbf40c1-7489-4d49-a2b3-32a6b81a34e4
    # Public IDs
    # 8f0c36ae-cc09-4f62-b670-72d94c86f18b
    # 369949d6-3b57-4c5e-a021-d30baf3e59e1


    print("Starting Game Creation and Update Testing 6")
    # print(Event.objects.get_active_events())
    # event1 = Event.objects.get_object_by_id("78d3de14-85d8-ee6d-bac5-f707c907dc08")
    # print(event1.home_team)
    # print(event1.away_team)
    #
    # event1 = Event.objects.get_object_by_id("85ccca87e453d00340982559fd50c443")
    # print(event1.home_team)
    # print(event1.away_team)


    #
    owner_id = "2e90977e-16b7-4e1d-b17c-1623fad1700a"
    player_2_id = "b56e01a2-cb8b-454f-b71a-b8a66ecc2930"
    owner = User.objects.get_object_by_id(owner_id)
    player_2 = User.objects.get_object_by_id(player_2_id)
    # print(owner)
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
    # print(GameSerializer(data=game1))


    print("Stopped Game Creation and Update Testing 6")


