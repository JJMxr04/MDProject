import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
import random
from core.user.models import User
from core.event.models import Event
from core.game.models import Game

class TieBreakerManager(AbstractManager):

    def set_owner_total(self,tiebreaker,total):
        tiebreaker.owner_total=total
        tiebreaker.save()

    def set_player_2_total(self,tiebreaker,total):
        tiebreaker.owner_total=total
        tiebreaker.save()

    def calculate_event_total(self, tiebreaker):
        event = tiebreaker.golden_game.event if tiebreaker.golden_game else None
        if event is None or event.home_score is None or event.away_score is None:
            return None
        tiebreaker.total = event.home_score + event.away_score
        tiebreaker.save(update_fields=["total"])
        return tiebreaker.total
    
    def calculate_winner(self, tiebreaker):
        total = self.calculate_event_total(tiebreaker=tiebreaker)
        if total is None:
            return self.calculate_winner_random(
                tiebreaker,
                tiebreaker.golden_game.owner,
                tiebreaker.golden_game.player_2,
            )
        owner_dif = abs(tiebreaker.owner_total - total)
        player_2_dif = abs(tiebreaker.player_2_total - total)

        if owner_dif < player_2_dif:
            tiebreaker.winner = tiebreaker.golden_game.owner
            tiebreaker.save()
            return tiebreaker.winner
        elif player_2_dif < owner_dif:
            tiebreaker.winner = tiebreaker.golden_game.player_2
            tiebreaker.save()
            return tiebreaker.winner
        else:
            return self.calculate_winner_random(tiebreaker,tiebreaker.golden_game.owner,tiebreaker.golden_game.player_2)




    def calculate_winner_random(self,tiebreaker,player_1,player_2):
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
    golden_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='tiebreaker_golden_game', blank=False, null=True,
                                    default=None)
    
    total = models.IntegerField(default=0)
    owner_total=models.IntegerField(default=0)
    player_2_total=models.IntegerField(default=0)
    
    objects = TieBreakerManager()

    class meta:
        db_table = "'core.tiebreaker'"

    def __str__(self):
        return f'Tiebreaker for: {self.golden_game.owner} vs {self.golden_game.player_2} '