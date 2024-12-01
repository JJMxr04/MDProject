import json
import os
import sys
from datetime import timedelta

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
from core.event.serializers.bookmaker import BookmakerSerializer
from core.event.serializers.market import MarketSerializer
from core.event.serializers.outcome import OutcomeSerializer
from core.event.models.bookmaker import Bookmaker
from core.event.models.market import Market
from core.event.models.outcome import Outcome
from django.utils import timezone


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

class DeleteEventCron():
    
    def delete_outdated_events(self):
        # Get the current time in UTC
        current_time = timezone.now()
        # Filter events that are not completed and have a commence_time that is 4 hours or more in the past
        outdated_events = Event.objects.filter(completed=False, commence_time__lt=current_time - timedelta(hours=4))
        print(outdated_events)
        # Delete the outdated events
        outdated_events.delete()


def delete_outdated_events():
    eventCron = DeleteEventCron()
    eventCron.delete_outdated_events()



