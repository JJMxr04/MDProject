import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from core.event.models import Outcome, Market
from datetime import datetime, timedelta
from django.utils import timezone
from core.user.models import User
from core.event.models import Event
from core.mail.models import Emails

class BetManager(AbstractManager):

    def create_bet(self):
        return self.create(market=None,owner_outcome=None,player_2_outcome=None)


    def calculate_owner_choice(self,bet,event):

        if not bet.owner_outcome :
            return False
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
            bet_points= bet.owner_outcome.point
            if bet.owner_outcome.name == 'over':
                if bet_points > points:
                    return True
                else:
                    return False
            if bet.owner_outcome.name == 'under':
                if bet_points < points:
                    return True
                else:
                    return False
        if bet.type == 'spreads':
            winner = event.winner
            points_diff = event.scores[0]['score'] - event.scores[1]['score']
            if bet.owner_outcome.point < 0:
                if winner != bet.owner_outcome.name:
                    return False
                else:
                    if abs(points_diff) < abs(bet.owner_outcome.point):
                        return False
                    else:
                        return True
            else:
                if winner == bet.owner_outcome.name:
                    return True
                elif abs(points_diff) < abs(bet.owner_outcome.point):
                    return True
                else: return False
    def calculate_player_2_choice(self,bet,outcome):
        if not bet.player_2_outcome :
            return False
        if bet.type == 'h2h':
            if bet.event.winner == 'tie':
                if bet.player_2_outcome.name== 'draw':
                    return True
                else:
                    return False
            elif bet.event.winner == bet.player_2_outcome.name:
                return True
            else:
                return False
        if bet.type == 'totals':
            scores = bet.event.scores
            points = scores[0]['score']+scores[1]['score']
            bet_points= bet.player_2_outcome.point
            if bet.player_2_outcome.name == 'over':
                if bet_points > points:
                    return True
                else:
                    return False
            if bet.player_2_outcome.name == 'under':
                if bet_points < points:
                    return True
                else:
                    return False
        if bet.type == 'spreads':
            winner = bet.event.winner
            points_diff = bet.event.scores[0]['score'] - bet.event.scores[1]['score']
            if bet.player_2_outcome.point < 0:
                if winner != bet.player_2_outcome.name:
                    return False
                else:
                    if abs(points_diff) < abs(bet.player_2_outcome.point):
                        return False
                    else:
                        return True
            else:
                if winner == bet.player_2_outcome.name:
                    return True
                elif abs(points_diff) < abs(bet.player_2_outcome.point):
                    return True
                else: return False
    def set_owner_outcome(self,bet,outcome):
        bet.market=outcome.market
        bet.owner_outcome = outcome
        bet.save()
    def set_player_2_outcome(self,bet,outcome):
        bet.player_2_outcome = outcome
        bet.save()
    def set_market(self,bet,market):
        bet.market = market
        bet.save()






class Bet(AbstractModel):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='bet_market', null=True,
                                      blank=True)
    owner_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_owner_outcome', null=True, blank=True)
    player_2_outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, related_name='bet_player_2_outcome', null=True,
                                      blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    objects = BetManager()
    class Meta:
        db_table = 'core.bet'
