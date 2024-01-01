import json
import requests
from django.core.serializers import serialize
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from core.event.models.event import Event
from core.event.serializers.event import EventSerializer, TeamScoreSerializer
from core.event.models.sport import Sport
import uuid

def write_json_to_file(data, filename):
    """
    Write JSON data to a file in a formatted way.

    Parameters:
    - data: The data to be written.
    - filename: The name of the file to write to.
    """
    json_data = json.dumps( data, indent=4)
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


class EventCron:
    sports_data = {}
    events = {}
    domain = "https://odds.p.rapidapi.com/v4/sports"
    headers = {
        "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
        "X-RapidAPI-Host": 'odds.p.rapidapi.com'
    }

    def get_sport_events(self, key):
        url = f"{self.domain}/{key}/scores"
        querystring = {"daysFrom": "3"}

        response = requests.get(url, headers=self.headers, params=querystring)

        if response.status_code == 200:
            api_data = response.json()
        else:
            print(f"API Request failed with status code: {response.status_code}")
            return Response("API Request failed", status=response.status_code)
        write_json_to_file(api_data,f'testfiles/originals/{key}.json')
        print(json.dumps(api_data,indent=4))
        for event in api_data:
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

    def update_all_events(self):
       active_sports = Sport.objects.get_active_sports()
       for sport in active_sports:
           self.get_sport_events(sport)


