import json
import os

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


class EventCron():
    sports_data = {}
    events = {}
    domain = f"https://{os.getenv("RAPID_ODDS_DOMAIN")}/v4/sports"
    headers = {
        "X-RapidAPI-Key": f"{os.getenv("RAPID_API_KEY")}",
        "X-RapidAPI-Host": f"{os.getenv("RAPID_ODDS_DOMAIN")}"
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
            existing_event = None
            try:
                existing_event = Event.objects.get(id=event_id)
                # The event exists, no need to reformat. Just update scores or other details.
                event_schema = EventSerializer(existing_event, data=event_data, partial=True)
            except ObjectDoesNotExist:
                # Event does not exist, format and create a new one.
                event_data['id'] = event_id
                event_data['title'] = sport.title
                event_data['group'] = sport.group
                event_data['description'] = sport.description
                event_data['home_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("home_team"), sport.title, sport.group)).data['id']
                event_data['away_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("away_team"), sport.title, sport.group)).data['id']
                event_schema = EventSerializer(data=event_data)

            # Validate and save
            if event_schema.is_valid():
                event_instance = event_schema.save()

                # Update scores or other details if needed
                if "scores" in event_data and existing_event and event_instance.completed != event_data.get("completed"):
                    score_data = event_data["scores"]
                    if score_data:
                        score1 = TeamScoreSerializer(data=score_data[0])
                        score2 = TeamScoreSerializer(data=score_data[1])

                        if score1.is_valid() and score2.is_valid():
                            Event.objects.get_event_state(
                                event_instance.id,
                                event_data.get("completed"),
                                score_data,
                                score1.validated_data,
                                score2.validated_data,
                            )
            else:
                print("Validation failed:", event_schema.errors)

        return Response("Success", status=status.HTTP_200_OK)

    def update_all_events(self):
        # print("Running Event Cron")
        active_sports = Sport.objects.get_active_sports()
        sports_num= len(active_sports)
        # print(print(f"Sport List Size = {sports_num}"))
        # x=0
        for sport in active_sports:
            # x+=1
            # print(f'Percentage Finished:{round((x/sports_num)*100)}%')
            self.get_sport_events(sport)
            # print(f'Percentage Finished:{round((x / sports_num) * 100)}%')
            # print(f"Finished: {sport}")

def update_all_events():
    eventCron = EventCron()
    eventCron.update_all_events()


