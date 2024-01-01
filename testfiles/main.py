# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
from django import setup
from django.core.exceptions import ObjectDoesNotExist
from django.core.serializers import serialize



# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()

# Other imports
import json
from core.event.serializers.event import EventSerializer, TeamScoreSerializer
from core.event.models.event import Event
from core.event.models.sport import Sport
from core.game.models import Game
from core.user.models import User
sport_model = Sport()
from core.event.crons.sportUpdate import SportCron
sport_cron = SportCron()

from core.event.crons.eventUpdate import EventCron
event_cron = EventCron()

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
    # print(api_data)
    api_data_json = json.loads(api_data)
    for event_json in api_data_json:
        event_data = event_json
        event_schema = EventSerializer(data=event_data)

        if event_schema.is_valid():
            event_instance = event_schema.validated_data
            print(event_instance)
            if event_instance['home_team'] is None or event_instance["away_team"] is None:
                continue
            try:
                existing_event = Event.objects.get_object_by_id(id=event_instance['id'])
            except ObjectDoesNotExist:
                existing_event = None

            if not existing_event:
                event_instance.save()

            if event_instance.completed:
                team_schema = TeamScoreSerializer()
                score1 = team_schema.load(data=json.loads(event_instance['scores'])[0])
                score2 = team_schema.load(data=json.loads(event_instance['scores'])[1])
                Event.get_sport_state(
                    event_instance['id'],
                    event_instance['completed'],
                    event_instance['scores'],
                    score1,
                    score2
                )

    return True


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

    print("Starting Event Creation Testing 5")

    # sport_cron.get_sports()
    sports = sport_cron.get_active_sports()
    # print(sports)
    # event_cron.get_sport_events("soccer_switzerland_superleague")
    # print(sports)
    for sport in sports:
        test_get_nfl_events(f'testfiles/originals/{sport}.json')
    print("Stopped Event Creation Testing 5")

    # IDs
    # 51387afd-c3f3-4750-83fd-db3ff20048b3
    # acbf40c1-7489-4d49-a2b3-32a6b81a34e4
    # Public IDs
    # 8f0c36ae-cc09-4f62-b670-72d94c86f18b
    # 369949d6-3b57-4c5e-a021-d30baf3e59e1


    # print("Starting Game Creation and Update Testing 6")
    # owner_id = "8f0c36ae-cc09-4f62-b670-72d94c86f18b"
    # player_2_id = "369949d6-3b57-4c5e-a021-d30baf3e59e1"
    # owner = User.objects.get_object_by_public_id(owner_id)
    # player_2 = User.objects.get_object_by_public_id(player_2_id)
    # # print(owner)
    # game = Game.objects.create_game(owner,player_2)
    #
    # data1 = {
    #     "event_id": "85ccca87e453d00340982559fd50c443",
    #     "player_choice": "Penn State Nittany Lions"
    # }
    # data2 = {
    #     "event_id": "85ccca87e453d00340982559fd50c443",
    #     "player_choice": "Ole Miss Rebels"
    # }
    #
    # Game.objects.update_by_id(game.id,owner,data1)
    # Game.objects.update_by_id(game.id, player_2, data2)
    #
    # print(game)
    #
    #
    # print("Stopped Game Creation and Update Testing 6")


