import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from core.user.models import User
from core.event.models import Event
from core.game.models import Game

class MatchManager(AbstractManager):
    def create_match(self,player_1,player_2 = None):
        return self.create(player_1=player_1,player_2=player_2)
    def accept_match(self,match_id,player_2):
        match =  self.get_object_by_id(id=match_id)


class Match(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_1_match')
    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_match',null=True,default=None)
    winner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='winner_match',null=True,default=None)
    match_state = models.CharField(max_length=10, default='created', null=False, blank=False)

    player_1_score = models.IntegerField(default=0, null=False, blank=False)
    player_2_score = models.IntegerField(default=0, null=False, blank=False)

    player_1_game_1 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_1', blank=False,null=True,default=None)
    player_1_game_1_completed = models.BooleanField(default=False)
    player_1_game_2 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_2', blank=False,null=True,default=None)
    player_1_game_2_completed = models.BooleanField(default=False)
    player_1_game_3 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_3', blank=False,null=True,default=None)
    player_1_game_3_completed = models.BooleanField(default=False)
    player_1_game_4 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_4', blank=False,null=True,default=None)
    player_1_game_4_completed = models.BooleanField(default=False)
    player_1_game_5 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_5', blank=False,null=True,default=None)
    player_1_game_5_completed = models.BooleanField(default=False)
    player_2_game_1 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_1', blank=False,null=True,default=None)
    player_2_game_1_completed = models.BooleanField(default=False)
    player_2_game_2 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_2', blank=False,null=True,default=None)
    player_2_game_2_completed = models.BooleanField(default=False)
    player_2_game_3 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_3', blank=False,null=True,default=None)
    player_2_game_3_completed = models.BooleanField(default=False)
    player_2_game_4 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_4', blank=False,null=True,default=None)
    player_2_game_4_completed = models.BooleanField(default=False)
    player_2_game_5 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_5', blank=False,null=True,default=None)
    player_2_game_5_completed = models.BooleanField(default=False)
    golden_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_golden_game_game', blank=False,null=True,default=None)
    golden_game_completed = models.BooleanField(default=False)
    objects = MatchManager()

    class meta:
        db_table = "'core.match'"