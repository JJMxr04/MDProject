# import json
# import requests
# from rest_framework.views import APIView
# from rest_framework.response import Response
# from rest_framework import status
# from django.core.exceptions import ObjectDoesNotExist
# from core.event.models.event import Event
# from core.event.serializers.event import EventSerializer, TeamScoreSerializer
#
#
# class EventCron:
#     sports_data = {}
#     events = {}
#     domain = "https://odds.p.rapidapi.com/v4/sports"
#     headers = {
#         "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
#         "X-RapidAPI-Host": 'odds.p.rapidapi.com'
#     }
#
#     def get_sport_events(self, key):
#         url = f"{self.domain}/{key}/scores"
#         querystring = {"daysFrom": "3"}
#
#         response = requests.get(url, headers=self.headers, params=querystring)
#
#         if response.status_code == 200:
#             api_data = response.json()
#         else:
#             print(f"API Request failed with status code: {response.status_code}")
#             return Response("API Request failed", status=response.status_code)
#
#         for event in api_data:
#             event_schema = EventSerializer(data=event)
#             if event_schema.is_valid():
#                 data = event_schema.validated_data
#                 if data.get('home_team') or data.get('away_team') is None:
#                     continue
#                 try:
#                     existing_event = Event.objects.get(id=data.get("id"))
#                 except ObjectDoesNotExist:
#                     event_game = Event(**data)
#                     event_game.save()
#                     continue
#
#                 if data.get('completed'):
#                     team_schema = TeamScoreSerializer(data=json.loads(event['scores'])[0])
#                     if team_schema.is_valid():
#                         score1 = team_schema.validated_data
#                     team_schema = TeamScoreSerializer(data=json.loads(event['scores'])[1])
#                     if team_schema.is_valid():
#                         score2 = team_schema.validated_data
#
#                     # Assuming get_sport_state is a method of your Event model
#                     existing_event.get_sport_state(data.get('completed'), score1, score2)
#
#         return Response("Success", status=status.HTTP_200_OK)
#
#
#
# class SportCron:
#     domain = 'https://odds.p.rapidapi.com/v4/sports'
#
#     sports_data = {}
#     events = {}
#     headers = {
#         "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
#         "X-RapidAPI-Host": 'odds.p.rapidapi.com'
#     }
#
#     def get_sports(self):
#         # Call your API here
#         api_url = self.domain
#
#         querystring = {"all": "true"}
#
#         response = requests.get(api_url, headers=self.headers, params=querystring)
#         # Replace with your actual API endpoint
#
#         # Process the API response (using Marshmallow schema)
#         if response.status_code == 200:
#             api_data = response.json()
#         else:
#             print(f"API Request failed with status code: {response.status_code}")
#             return False
#
#         for sport in api_data:
#             sport_schema = SportSchema()
#             data = sport_schema.load(data=sport)
#
#             if Sport.get_sport_state(data.get('key'),data.get('active'),data.get('has_outrights')):
#                 #returns true if it was found and modified
#                 #returns false if there is no sport with that key
#                 continue
#             else:
#                 sport_temp = Sport(**data)
#                 sport_temp.save()
#         write_json_to_file(self.sports_data,"sports.json")
#         return True
#
