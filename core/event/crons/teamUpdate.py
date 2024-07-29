import os
import logging
import json
import requests
from django.conf import settings
from django.http import Http404
from core.event.models import Team
from django.core.files.base import ContentFile

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

logging.basicConfig(level=logging.INFO)

class TeamCron:
    def create_team(self, team_name, title, group, team_id, logo_content, country, country_code):
        return Team.objects.create_team(team_name, title, group, team_id, logo_content, country, country_code)

    def get_team_api(self, team_name):
        url = "https://sofascore.p.rapidapi.com/teams/search"
        querystring = {"name": f"{team_name}"}
        headers = {
            "X-RapidAPI-Key": "your_rapidapi_key",
            "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            data = response.json()
            if data['teams']:
                country = data['teams'][0].get('country', {}).get('name', "NoCountry")
                country_code = data['teams'][0].get('country', {}).get('alpha2', "NoCountry")
                team_id = data['teams'][0]['id']
                return country, country_code, team_id
            else:
                return None, None, None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None, None, None

    def get_logo(self, team_id):
        url = "https://sofascore.p.rapidapi.com/teams/get-logo"
        querystring = {"teamId": team_id}
        headers = {
            "X-RapidAPI-Key": "your_rapidapi_key",
            "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers, params=querystring)
        return None
        # if response.status_code == 200 and response.content:
        #     return ContentFile(response.content)
        # else:
        #     print(f"Error: {response.status_code} - {response.text}")
        #     return None

    def check_team(self, team_name, title, group):
        try:
            team_search = Team.objects.get_object_by_team_name(team_name)
            return team_search
        except Http404:
            country, country_code, team_id = self.get_team_api(team_name)
            if team_id is not None:
                logo_content = self.get_logo(team_id)
                return self.create_team(team_name, title, group, team_id, logo_content, country, country_code)
            else:
                return self.create_team(team_name, title, group, None, None, country, country_code)
