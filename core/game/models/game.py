import uuid
from django.db import models
from django.utils import timezone
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404

class GameManager(AbstractManager):
    # def create_game(self, owner, player_2, match_id, commence_time=None, deadline_time=None, completed=False,
    #                home_team=None, away_team=None, winner=None):
    #     return self.create(owner=owner, player_2=player_2, match_id=match_id, commence_time=commence_time,
    #                         deadline_time=deadline_time, completed=completed, home_team=home_team,
    #                         away_team=away_team, winner=winner)
    def create_game(self, owner, player_2, commence_time=None, deadline_time=None, completed=False,
                   home_team=None, away_team=None, winner=None):
        return self.create(owner=owner, player_2=player_2,  commence_time=commence_time,
                            deadline_time=deadline_time, completed=completed, home_team=home_team,
                            away_team=away_team, winner=winner)

class Game(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='owned_games')
    player_2 = models.ForeignKey('User', on_delete=models.CASCADE, related_name='games_as_player_2')
    # match_id = models.CharField(max_length=255)
    commence_time = models.DateTimeField(default=None, null=True, blank=True)
    deadline_time = models.DateTimeField(default=None, null=True, blank=True)
    completed = models.BooleanField(default=False)
    home_team = models.CharField(max_length=200, default=None, null=True, blank=True)
    away_team = models.CharField(max_length=200, default=None, null=True, blank=True)
    winner = models.CharField(max_length=200, default=None, null=True, blank=True)
    owner_choice = models.CharField(max_length=200, default=None, null=True, blank=True)
    player_2_choice = models.CharField(max_length=200, default=None, null=True, blank=True)
    player_2 = models.ForeignKey('User', on_delete=models.CASCADE, related_name='games_as_player_2')
    objects = GameManager()

    class meta:
        db_table = "'core.game'"


# Create your models here.
