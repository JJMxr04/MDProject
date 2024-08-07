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
from core.event.crons.teamUpdate import TeamCron
from core.event.serializers.team import TeamSerializer

teamCron = TeamCron()

def write_json_to_file(data, filename):
    json_data = json.dumps(data, indent=4)
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

class EventCron():
    sports_data = {}
    events = {}
    domain = "https://odds.p.rapidapi.com/v4/sports"
    headers = {
        "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
        "X-RapidAPI-Host": 'odds.p.rapidapi.com'
    }

    def get_sport_events(self, sport):
        key = sport.key
        url = f"{self.domain}/{key}/scores"
        querystring = {"daysFrom": "3"}

        response = requests.get(url, headers=self.headers, params=querystring)

        if response.status_code != 200:
            return Response(f"API Request failed with status code: {response.status_code}", status=status.HTTP_400_BAD_REQUEST)

        api_data = response.json()

        for event_data in api_data:
            if event_data.get("away_team") is None or event_data.get("home_team") is None:
                continue

            event_id = uuid.UUID(event_data.get("id"))
            eventID = f'{event_data.get("id")}'
            existing_event = None

            try:
                existing_event = Event.objects.get(id=eventID)
                event_schema = EventSerializer(existing_event, data=event_data, partial=True)
            except Event.DoesNotExist:
                event_data['id'] = event_id
                event_data['title'] = sport.title
                event_data['group'] = sport.group
                event_data['description'] = sport.description
                event_data['home_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("home_team"), sport.title, sport.group)).data['id']
                event_data['away_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("away_team"), sport.title, sport.group)).data['id']
                event_schema = EventSerializer(data=event_data)

            if event_schema.is_valid():
                event = event_schema.save()
                data = event_schema.validated_data

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
            else:
                print("Validation failed:", event_schema.errors)
        return Response("Success", status=status.HTTP_200_OK)

    def update_all_events(self):
        active_sports = Sport.objects.get_active_sports()
        for sport in active_sports:
            self.get_sport_events(sport)

def update_all_events():
    eventCron = EventCron()
    eventCron.update_all_events()
