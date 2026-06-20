import asyncio
import logging
import math
import unittest
from datetime import datetime, timedelta

from django.utils import timezone

from core.tournament.models.tournament import Player
from core.tournament.unit_tests.tests.Tourney_Simulator_3 import TourneyTest

logger = logging.getLogger(__name__)
class tournament_test_3():
    databases = ['default', 'test_mirror']

    first_round_game_picks ={
        'data1' : {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Miami Dolphins"
        },
        'data2': {
            "event_id": "484bc5582bb44ab79a1e942cf8762eda",
            "player_choice": "Tennessee Titans"
        },
        'data1_gg' : {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "New York Giants"
        },
        'data2_gg' : {
            "event_id": "ea43090cd4cc2eb2fb98ba3847aba986",
            "player_choice": "Green Bay Packers"
        }
    }

    second_round_game_picks = {
        'data1': {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Philadelphia Eagles"
        },
        'data2': {
            "event_id": "5e766a287ba24d40d9e40aa41efe19de",
            "player_choice": "Buffalo Bills"
        },
        'data1_gg': {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Kansas City Chiefs"
        },
        'data2_gg': {
            "event_id": "c491f05b066449d95732c4f52ac57e66",
            "player_choice": "Las Vegas Raiders"
        }
    }

    third_round_game_picks = {
        'data1': {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Miami Dolphins"
        },
        'data2': {
            "event_id": "eb77c9dad13ef82ba5ff4dcf439d3bab",
            "player_choice": "Baltimore Ravens"
        },
        'data1_gg': {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Los Angeles Chargers"
        },
        'data2_gg': {
            "event_id": "c1b7e562062eb3bac053a2f5ecf399f9",
            "player_choice": "Minnesota Vikings"
        }
    }

    fourth_round_game_picks = {
        'data1': {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Dallas Cowboys"
        },
        'data2': {
            "event_id": "b2eeb176fc9adfc63b9098b313905792",
            "player_choice": "Seattle Seahawks"
        },
        'data1_gg': {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Pittsburgh Steelers"
        },
        'data2_gg': {
            "event_id": "76ae384526017414d68d617bf80b8aab",
            "player_choice": "Arizona Cardinals"
        }
    }

    fifth_round_game_picks = {
        'data1': {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "New York Jets"
        },
        'data2': {
            "event_id": "d9498cb661062746dfc500a20c3a87e8",
            "player_choice": "Atlanta Falcons"
        },
        'data1_gg': {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "New Orleans Saints"
        },
        'data2_gg': {
            "event_id": "41c4d77b6a910a6b2364fbeb51dba059",
            "player_choice": "Detroit Lions"
        }
    }

    sixth_round_game_picks = {
        'data1': {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Tennessee Titans"
        },
        'data2': {
            "event_id": "6cd4bff8b0950234be09e6c0acda7b95",
            "player_choice": "Indianapolis Colts"
        },
        'data1_gg': {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Washington Commanders"
        },
        'data2_gg': {
            "event_id": "5e0c5b79c3cb142f3361ade464174b68",
            "player_choice": "Miami Dolphins"
        }

    }

    seventh_round_game_picks = {
        'data1': {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Houston Texans"
        },
        'data2': {
            "event_id": "53c6da53a7ba5f06aae182ee5ce38616",
            "player_choice": "Denver Broncos"
        },
        'data1_gg': {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "New England Patriots"
        },
        'data2_gg': {
            "event_id": "ad1bbe3e94716ca03c3059092cbd1eee",
            "player_choice": "Los Angeles Chargers"
        }

    }

    def __init__(self,max_players,tourney_name):
        super().__init__()
        self.max_players = max_players
        self.tourney_name = tourney_name
        self.tourny_Sim = TourneyTest(max_players=self.max_players,tourney_name=self.tourney_name)
        self.tourny_Sim.run_test()
        self.tournament = self.tourny_Sim.tournament_record
