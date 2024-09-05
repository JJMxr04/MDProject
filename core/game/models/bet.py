import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from core.event.models import Outcome
from datetime import datetime, timedelta
from django.utils import timezone
from core.user.models import User
from core.event.models import Event
from core.mail.models import Emails

class BetManager(AbstractManager):


    def calculate_owner_choice(self,bet,event):
        if bet.type == 'h2h':
            if event.winner == 'tie':
                if bet.owner_outcome.name== 'draw':
                    return True
                else:
                    return False
            elif event.winner == bet.owner_outcome.name:
                return True
            else:
                return False
        if bet.type == 'totals':
            scores = event.scores
            points = scores[0]['score']+scores[1]['score']
            bet_points= bet.owner.outcome.point
            if bet.owner.outcome.name == 'over':
                if bet_points > points:
                    return True
                else:
                    return False
            if bet.owner.outcome.name == 'under':
                if bet_points < points:
                    return True
                else:
                    return False
        if bet.type == 'spreads':
            pass
    def calculate_player_2_choice(self,bet,outcome):
        pass
    def set_owner_outcome(self,bet,outcome):
        bet.owner_outcome = outcome
        bet.save()
    def set_player_2_outcome(self,bet,outcome):
        bet.player_2_outcome = outcome
        bet.save()
    def set_selected_outcome(self,bet,outcome,market):
        bet.selected_outcome = outcome
        bet.type = market.key
        bet.save()







class Bet(AbstractModel):
    type= models.CharField(max_length=15, null=True, blank=True)
    selected_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_selected_outcome', null=True,
                                      blank=True)
    owner_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_owner_outcome', null=True, blank=True)
    player_2_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_player_2_outcome', null=True,
                                      blank=True)
    correct_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_correct_outcome', null=True,
                                      blank=True)



    objects = BetManager
    class Meta:
        db_table = 'core.bet'
