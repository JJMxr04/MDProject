# Initialize Django environment
import os
import time  # For rate limiting
from django import setup
from tqdm import tqdm  # For progress bar

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CoreRoot.settings")
setup()

# Import required Django modules and settings
from django.conf import settings
import logging
from core.event.models.team import Team
import requests

# Set up logging to capture errors and warnings
logging.basicConfig(level=logging.WARNING)

# Function to check if a logo file exists for a team
def logo_exists(team_id, country, title, team_name):
    media_root = settings.MEDIA_ROOT
    directory_path = os.path.join(media_root, 'teamlogos', country, title, team_name)
    filename = os.path.join(directory_path, f"{team_id}.png")
    return os.path.exists(filename)  # Return True if the logo file exists

# Function to fetch the team logo from an API
def fetch_team_logo(team_id):
    url = "https://sofascore.p.rapidapi.com/teams/get-logo"
    querystring = {"teamId": team_id}
    headers = {
        "X-RapidAPI-Key": "5e67f9e23emsh42a3758bd291b0bp1ed121jsnc118f34dcfda",
        "X-RapidAPI-Host": "sofascore.p.rapidapi.com"
    }
    response = requests.get(url, headers=headers, params=querystring)
    if response.status_code == 204:# Check if the request was successful
        return response.content  # Return the raw logo data
    else:
        logging.warning(f"Error fetching logo for team {team_id}: {response.status_code} - {response.text}")
        return None  # Return None if there was an error

# Function to save the fetched logo to the correct path
def save_team_logo(team_id, country, title, team_name, logo_data):
    try:
        # Construct the directory path and ensure it exists
        media_root = settings.MEDIA_ROOT
        directory_path = os.path.join(media_root, 'teamlogos', country, title, team_name)

        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)  # Create the directory if it doesn't exist

        # Save the logo file
        filename = os.path.join(directory_path, f"{team_id}.png")
        logging.info(f"Attempting to write logo to: {filename}")

        with open(filename, 'wb') as file:
            file.write(logo_data)  # Write the raw image data to the file

        logging.info(f"Successfully saved logo to: {filename}")

        # Return the relative path
        return os.path.relpath(filename, media_root)

    except Exception as e:
        logging.error(f"Error saving logo for team {team_id}: {e}")
        return None

# Function to ensure the team logo is present; if not, fetch and save it
def ensure_team_logo(team):
    # Handle potential missing fields with defaults
    country = team.country or "NoCountry"
    title = team.title or "NoTitle"
    team_name = team.team_name or "NoTeam"
    team_id = team.team_id or "NoID"

    if not logo_exists(team_id, country, title, team_name):  # If the logo doesn't exist
        logging.info(f"Logo file does not exist for {team_name}, fetching from API.")

        # Fetch the team logo from the API with rate limiting
        time.sleep(1)  # Introduce a 1-second delay between requests to avoid rate limit issues
        logo_data = fetch_team_logo(team_id)  # Get the raw logo data

        if logo_data:
            relative_path = save_team_logo(team_id, country, title, team_name, logo_data)  # Save it
            team.logo_url = os.path.join(settings.MEDIA_URL, relative_path)  # Set the logo URL
            team.save()  # Persist the changes
            logging.info(f"Logo fetched and saved for {team_name}")
            return True
        else:
            logging.warning(f"Failed to fetch logo for {team_name}")
            return False

# Function to update the `logo_url` field for all teams with a progress bar
def update_logo_urls():
    teams = Team.objects.all()  # Fetch all teams from the database
    total_teams = teams.count()  # Get the total count for the progress bar

    # Iterate through all teams with a progress bar
    for team in tqdm(teams, total=total_teams, desc="Updating logo URLs"):
        if ensure_team_logo(team):# Ensure the logo exists for each team
            continue

        # Update the `logo_url` with the relative path
        media_root = settings.MEDIA_ROOT
        directory_path = os.path.join(media_root, 'teamlogos', team.country, team.title, team.team_name)
        filename = os.path.join(directory_path, f"{team.team_id}.png")
        new_logo_url = os.path.relpath(filename, media_root)

        # Set the relative path in `logo_url`
        team.logo_url = os.path.join(settings.MEDIA_URL, new_logo_url)
        team.save()  # Persist the changes

# Run the update function when the script is executed
if __name__ == '__main__':
    update_logo_urls()  # Update the `logo_url` fields for all teams
