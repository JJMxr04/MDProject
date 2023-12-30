import json
import requests
from core.event.models.sport import Sport
from core.event.serializers.sport import SportSerializer, TeamScoreSerializer


class SportCron:
    domain = 'https://odds.p.rapidapi.com/v4/sports'

    sports_data = {}
    events = {}
    headers = {
        "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
        "X-RapidAPI-Host": 'odds.p.rapidapi.com'
    }

    def get_sports(self):
        # Call your API here
        api_url = self.domain

        querystring = {"all": "true"}

        response = requests.get(api_url, headers=self.headers, params=querystring)
        # Replace with your actual API endpoint

        # Process the API response (using Marshmallow schema)
        if response.status_code == 200:
            api_data = response.json()
        else:
            print(f"API Request failed with status code: {response.status_code}")
            return False
        sport_ser = SportSerializer()
        for sport in api_data:
            data = sport_ser.to_internal_value(sport)

            if Sport.objects.get_sport_state(data.get('key'),data.get('active'),data.get('has_outrights')):
                #returns true if it was found and modified
                #returns false if there is no sport with that key
                continue
            else:
                sport_temp = Sport(**data)
                sport_temp.save()
        return True

    def get_active_sports(self):
        return Sport.objects.get_active_sports()
