import json
import requests
from django.core.serializers import serialize
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from core.match.models import Match
import uuid
from django.db.models import F


class MatchCron:

    def completeMatches(self):
        today = timezone.now().date()
        # Use __date to extract the date part from end_date for comparison
        matches = Match.objects.filter(end_date__date__lte=today, match_state='accepted')

        if not matches.exists():
            print("No matches found.")
        else:
            print(f"{matches.count()} matches found.")
            for match in matches:
                Match.objects.calculate_winner(match)
