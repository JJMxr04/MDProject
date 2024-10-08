import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
import random
from core.user.models import User

class TieBreakerManager(AbstractManager):


    def calculate_winner(self,tiebreaker,player_1,player_2):
        lucky_num =random.randint(1, 2)
        if lucky_num == 1:
            tiebreaker.winner = player_1
        if lucky_num == 2:
            tiebreaker.winner = player_2
        tiebreaker.save()
        return tiebreaker.winner


class TieBreaker(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    winner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='winner_tiebreaker', null=True, default=None)
    objects = TieBreakerManager()
    class meta:
        db_table = "'core.tiebreaker'"

    def __str__(self):
        return f'{self.player_1} vs {self.player_2} - {self.match_state}'