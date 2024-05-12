#This Model does not run on a timer but is used with the crons.

from django.conf import settings  # Import the Django settings module
import os
import logging
#from dotenv import load_dotenv
#load_dotenv()
import json

import requests

from django.http import Http404
from core.event.models  import Team
team = Team()

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


logging.basicConfig(level=logging.INFO)

def write_image(content, country, title, team_name, team_id):
    try:
        # Define the base media directory using Django's MEDIA_ROOT setting
        media_root = settings.MEDIA_ROOT  # Get MEDIA_ROOT from Django settings

        # Construct the directory path relative to MEDIA_ROOT
        directory_path = os.path.join(media_root, 'teamlogos', country, title, team_name)

        # Create the directories if they don't exist
        os.makedirs(directory_path, exist_ok=True)

        # Define the filename with the given team_id
        filename = os.path.join(directory_path, f"{team_id}.png")

        # Open the file in binary mode and write the image content
        with open(filename, "wb") as file:
            file.write(content)

        # logging.info(f"Image saved to {filename}")  # Log success
        return filename  # Return the full file path to the saved image

    except Exception as e:
        logging.error(f"Error writing image: {e}")  # Log errors
        return None  # Return None to indicate failure


class TeamCron():
    # This Model does not run on a timer but is used with the crons.

    def create_team(self, team_name, title, group, team_id, logo_url, country, country_code):
        return Team.objects.create_team(team_name, title, group, team_id, logo_url, country, country_code)

    def create_save_logo(self,team_name, title, team_id, country, content):
        # Use MEDIA_ROOT to construct the correct path
        media_root = settings.MEDIA_ROOT

        # Call the write_image function to save the content
        filename = write_image(content, country, title, team_name, team_id)

        # Construct the relative URL from MEDIA_URL and the filename
        relative_url = os.path.relpath(filename, media_root)

        # Create the full URL using MEDIA_URL
        full_url = os.path.join(settings.MEDIA_URL, relative_url)  # This should not include a domain

        return full_url

    def get_team_api(self, team_name):
        url = "https://sofascore.p.rapidapi.com/teams/search"
        querystring = {"name": f"{team_name}"}
        headers = {
            "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
            "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers, params=querystring)


        if response.status_code == 200:
            data = response.json()
            # write_json_to_file(data, f'testfiles/teams/teams_json.json')
            if data['teams']:
                if data['teams'][0]['country']:
                    country = data['teams'][0]['country']['name']
                    country_code = data['teams'][0]['country']['alpha2']
                else:
                    country = "NoCountry"
                    country_code = "NoCountry"
                team_id = data['teams'][0]['id']
                # if len(data) > 1:
                #     country = data[0]['country']['name']
                #     country_code = data[0]['country']['alpha2']
                #     team_id = data[0]['id']
                # else:
                #     country = data.get('country').get('name')
                #     country_code = data['country']['alpha2']
                #     team_id = data['id']
                return country, country_code, team_id
            else:
                return None,None,None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            # print(f"Counld Find {team_name}")
            return None,None,None
            # raise Http404("Team not found")

    def get_logo(self, team_id, team_name, title, country):
        url = "https://sofascore.p.rapidapi.com/teams/get-logo"
        querystring = {"teamId": team_id}
        headers = {
            "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
            "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
        }
        response = requests.get(url, headers=headers, params=querystring)
        # Check if the request was successful (status code 200)
        if response.status_code == 200 or response.status_code == 204:
            # Get the content of the response (image data)
            # data = response.json()
            # write_json_to_file(data, f'testfiles/teams/teams_logos.json')
            if response.content:
                return self.create_save_logo(team_name, title, team_id, country, response.content)
            else:
                print(f"Error: {response.status_code} - {response.text} - data: {response.content}")
                return None
        else:
            print(f"Error: {response.status_code} - {response.text}")
            #raise Http404("Failed to get logo")
            # print(f"Failed to get logo:{team_name}:{team_id}")
            return None

    def check_team(self, team_name, title, group):
        try:
            team_search = Team.objects.get_object_by_team_name(team_name)
            # print(f"Team {team_name} exists1")
            return team_search
        except Http404:
            # print(f"Team {team_name} does not exist")
            # Handle the case where the team does not exist
            country, country_code, team_id = self.get_team_api(team_name)
            team = Team.objects.get_object_by_team_id(team_id)
            if team is None:
                # print(f"Team {team_name} does not exist")
                if team_id is not None:
                    logo_url = self.get_logo(team_id, team_name, title, country)
                else:
                    logo_url = None
                return self.create_team(team_name, title, group, team_id, logo_url, country, country_code)
            else:
                # print(f"Team {team} exists 1")
                return team





