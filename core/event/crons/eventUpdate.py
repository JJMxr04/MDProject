
import json
import os
import sys

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

from datetime import datetime, timezone

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
        "X-RapidAPI-Key": f"{os.environ.get("RAPID_API_KEY")}",
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
            # fixed the event updates that calcualte the winner but now the api is broken
            event_id = uuid.UUID(event_data.get("id"))
            eventID = f'{event_data.get("id")}'
            existing_event = None

            try:
                existing_event = Event.objects.get(id=eventID)
                existing_event_completed = existing_event.completed
                event_schema = EventSerializer(existing_event, data=event_data, partial=True)
                if event_schema.is_valid():
                    event_instance = event_schema.save()
                    if event_data["scores"] and (not existing_event_completed) and event_instance.completed:
                        score_data = event_data["scores"]

                        if score_data:
                            score1 = TeamScoreSerializer(data=score_data[0])
                            score2 = TeamScoreSerializer(data=score_data[1])

                            if score1.is_valid() and score2.is_valid():
                                Event.objects.get_event_state(
                                    event_instance.id,
                                    event_data["completed"],
                                    score_data,
                                    score1.validated_data,
                                    score2.validated_data,
                                )
                else:
                    print("Validation failed:", event_schema.errors)

            except Event.DoesNotExist:
                event_data['id'] = event_id
                event_data['title'] = sport.title
                event_data['group'] = sport.group
                event_data['description'] = sport.description
                event_data['home_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("home_team"), sport.title, sport.group)).data['id']
                event_data['away_team_team'] = TeamSerializer(teamCron.check_team(event_data.get("away_team"), sport.title, sport.group)).data['id']
                event_schema = EventSerializer(data=event_data)

                if event_schema.is_valid():
                    event_instance = event_schema.save()
                    if event_instance.completed:
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


        return Response("Success", status=status.HTTP_200_OK)

    def get_upcoming_odds(self):

        url = f"{self.domain}/upcoming/odds"
        querystring = {"daysFrom": "3", "regions": {"us"},
                       "markets": {"h2h,spreads,totals"}}

        response = requests.get(url, headers=self.headers, params=querystring)
        if response.status_code != 200:
            return Response(f"API Request failed with status code: {response.status_code}",
                            status=status.HTTP_400_BAD_REQUEST)

        api_data = response.json()

        for event_data in api_data:
            if event_data.get("away_team") is None or event_data.get("home_team") is None:
                continue
            event_id = uuid.UUID(event_data.get("id"))
            eventID = f'{event_data.get("id")}'

            # Fetch or create the event instance
            event_instance, created = Event.objects.get_or_create(id=eventID)

            for bookmaker_data in event_data['bookmakers']:
                bookmaker_id = bookmaker_data.get('id')

                # Handle last_update to ensure it's in the correct format
                last_update = bookmaker_data.get('last_update')
                if isinstance(last_update, datetime):
                    last_update_str = last_update.isoformat()
                else:
                    last_update_str = last_update or timezone.now().isoformat()

                bookmaker_instance, _ = Bookmaker.objects.get_or_create(
                    id=bookmaker_id,
                    defaults={'event': event_instance, 'last_update': last_update_str, 'key': bookmaker_data.get('key'),
                              'title': bookmaker_data.get('title')}
                )

                # Process markets - Ensure only one market with the same key and bookmaker
                for market_data in bookmaker_data.get('markets', []):
                    market_key = market_data.get('key')

                    try:
                        market_instance = Market.objects.get(key=market_key, bookmaker=bookmaker_instance)
                    except Market.MultipleObjectsReturned:
                        market_instance = Market.objects.filter(key=market_key, bookmaker=bookmaker_instance).first()
                    except Market.DoesNotExist:
                        market_instance = Market.objects.create(
                            key=market_key,
                            bookmaker=bookmaker_instance,
                            last_update=last_update_str  # Ensure last_update is set
                        )

                    # Update the market instance
                    market_serializer = MarketSerializer(market_instance, data=market_data, partial=True)
                    if market_serializer.is_valid():
                        market_serializer.save()
                    else:
                        print("Validation errors in market:")
                        print(market_serializer.errors)

                    # Process outcomes for the market
                    for outcome_data in market_data.get('outcomes', []):
                        outcome_name = outcome_data.get('name')
                        outcome_instance, _ = Outcome.objects.get_or_create(
                            name=outcome_name,
                            market=market_instance,
                            defaults=outcome_data
                        )

                        # Update the outcome instance if needed
                        outcome_serializer = OutcomeSerializer(outcome_instance, data=outcome_data, partial=True)
                        if outcome_serializer.is_valid():
                            outcome_serializer.save()
                        else:
                            print("Validation errors in outcome:")
                            print(outcome_serializer.errors)

                event_instance.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)

    def get_sport_odds(self, sport):
        url = f"{self.domain}/{sport.key}/odds"
        querystring = {"daysFrom": "3", "regions": {"us"}, "markets": {"h2h,spreads,totals"}}

        response = requests.get(url, headers=self.headers, params=querystring)
        if response.status_code != 200:
            return Response(f"API Request failed with status code: {response.status_code}",
                            status=status.HTTP_400_BAD_REQUEST)

        api_data = response.json()

        for event_data in api_data:
            if event_data.get("away_team") is None or event_data.get("home_team") is None:
                continue
            event_id = uuid.UUID(event_data.get("id"))
            eventID = f'{event_data.get("id")}'

            # Fetch or create the event instance
            event_instance, created = Event.objects.get_or_create(id=eventID)

            for bookmaker_data in event_data['bookmakers']:
                bookmaker_id = bookmaker_data.get('id')

                # Handle last_update to ensure it's in the correct format
                last_update = bookmaker_data.get('last_update')
                if isinstance(last_update, datetime):
                    last_update_str = last_update.isoformat()
                else:
                    last_update_str = last_update or timezone.now().isoformat()

                bookmaker_instance, _ = Bookmaker.objects.get_or_create(
                    id=bookmaker_id,
                    defaults={'event': event_instance, 'last_update': last_update_str,'key':bookmaker_data.get('key'),'title':bookmaker_data.get('title')}
                )

                # Process markets - Ensure only one market with the same key and bookmaker
                for market_data in bookmaker_data.get('markets', []):
                    market_key = market_data.get('key')

                    try:
                        market_instance = Market.objects.get(key=market_key, bookmaker=bookmaker_instance)
                    except Market.MultipleObjectsReturned:
                        market_instance = Market.objects.filter(key=market_key, bookmaker=bookmaker_instance).first()
                    except Market.DoesNotExist:
                        market_instance = Market.objects.create(
                            key=market_key,
                            bookmaker=bookmaker_instance,
                            last_update=last_update_str  # Ensure last_update is set
                        )

                    # Update the market instance
                    market_serializer = MarketSerializer(market_instance, data=market_data, partial=True)
                    if market_serializer.is_valid():
                        market_serializer.save()
                    else:
                        print("Validation errors in market:")
                        print(market_serializer.errors)

                    # Process outcomes for the market
                    for outcome_data in market_data.get('outcomes', []):
                        outcome_name = outcome_data.get('name')
                        outcome_instance, _ = Outcome.objects.get_or_create(
                            name=outcome_name,
                            market=market_instance,
                            defaults=outcome_data
                        )

                        # Update the outcome instance if needed
                        outcome_serializer = OutcomeSerializer(outcome_instance, data=outcome_data, partial=True)
                        if outcome_serializer.is_valid():
                            outcome_serializer.save()
                        else:
                            print("Validation errors in outcome:")
                            print(outcome_serializer.errors)

                event_instance.save()
        return Response({"status": "success"}, status=status.HTTP_200_OK)

    def update_all_events(self):
        broken_leagues=[
            'americanfootball_ncaaf_championship_winner',
            'americanfootball_nfl_super_bowl_winner',
            # 'baseball_mlb',
            'baseball_mlb_preseason',
            'baseball_mlb_world_series_winner',
            'baseball_milb',
            'baseball_npb',
            'baseball_kbo',
            'baseball_ncaa',
            'basketball_nba_championship_winner',
            'basketball_ncaab_championship_winner',
            'basketball_nbl',
            'boxing_boxing',
            'cricket_big_bash',
            'cricket_caribbean_premier_league',
            'cricket_icc_world_cup',
            'cricket_international_t20',
            'cricket_ipl',
            'cricket_odi',
            'cricket_psl',
            'cricket_t20_blast',
            'cricket_test_match',
            'golf_masters_tournament_winner',
            'golf_pga_championship_winner',
            'golf_the_open_championship_winner',
            'golf_us_open_winner',
            'icehockey_nhl_championship_winner',
            'icehockey_sweden_hockey_league',
            'icehockey_sweden_allsvenskan',
            'lacrosse_pll',
            'mma_mixed_martial_arts',
            'politics_us_presidential_election_winner',
            'soccer_africa_cup_of_nations',
            'soccer_fifa_world_cup_winner',
            'soccer_uefa_nations_league',
            'tennis_atp_aus_open_singles',
            'tennis_atp_canadian_open',
            'tennis_atp_china_open',
            'tennis_atp_cincinnati_open',
            'tennis_atp_french_open',
            'tennis_atp_paris_masters',
            'tennis_atp_shanghai_masters',
            'tennis_atp_us_open',
            'tennis_atp_wimbledon',
            'tennis_wta_aus_open_singles',
            'tennis_wta_canadian_open',
            'tennis_wta_china_open',
            'tennis_wta_cincinnati_open',
            'tennis_wta_french_open',
            'tennis_wta_us_open',
            'tennis_wta_wimbledon',
            'tennis_wta_wuhan_open',
        ]
        active_sports = Sport.objects.get_active_sports()
        for sport in active_sports:
            if sport.key not in broken_leagues:
                self.get_sport_events(sport)
                self.get_sport_odds(sport)
            
def update_all_events():
    eventCron = EventCron()
    eventCron.update_all_events()
    # eventCron.get_upcoming_odds()
