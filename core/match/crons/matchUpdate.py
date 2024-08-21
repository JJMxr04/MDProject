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


class MatchCron:

    def completeMatches(self):
        today = timezone.now().date()
        matches = Match.objects.filter(end_date__lte=today, match_state='completed')
        print(matches)
        for match in matches:
            Match.objects.calculate_winner(match)
