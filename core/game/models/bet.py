import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from core.event.models import Outcome, Market
from datetime import datetime, timedelta
from django.utils import timezone
from core.user.models import User
from core.event.models import Event
from core.mail.models import Emails
import ast
import json
import re
import ast

class BetManager(AbstractManager):

    def create_bet(self,market=None):
        return self.create(
            market=market,
            owner_outcome=None,
            player_2_outcome=None,
            owner_outcome_correct=False,
            player_2_outcome_correct=False,
            is_processed=False
        )

    def calculate_owner_choice(self, bet, event):
        if not bet.owner_outcome:
            return False

        result = False
        if bet.market.key == 'h2h':
            if event.winner == 'tie':
                result = bet.owner_outcome.name == 'draw'
            else:
                result = event.winner == bet.owner_outcome.name

        elif bet.market.key == 'totals':
            try:
                scores = event.scores
                points = int(scores[0]['score']) + int(scores[1]['score'])
                bet_points = bet.owner_outcome.point
                if bet.owner_outcome.name == 'Over':
                    result = (points > bet_points)
                if bet.owner_outcome.name == 'Under':
                    result = bet_points > points
            except (ValueError, TypeError, IndexError) as e:
                return False

        elif bet.market.key == 'spreads':
            try:
                scores = list(event.scores)
                points_diff = int(scores[0]['score']) - int(scores[1]['score'])
                winner = event.winner

                if bet.owner_outcome.point < 0:
                    if winner != bet.owner_outcome.name:
                        result =  False
                    else:
                        result = abs(points_diff) >= abs(bet.owner_outcome.point)
                else:
                    if winner == bet.owner_outcome.name:
                        result = True
                    else:
                        result = abs(points_diff) < abs(bet.owner_outcome.point)
            except (ValueError, TypeError, IndexError) as e:
                return False

        # Store the result
        bet.owner_outcome_correct = result
        bet.is_owner_outcome_processed = True
        bet.save()
        return result

    def calculate_player_2_choice(self, bet, event):
        if not bet.player_2_outcome:
            return False

        result = False
        if bet.market.key == 'h2h':
            if event.winner == 'tie':
                result = bet.player_2_outcome.name == 'draw'
            else:
                result = event.winner == bet.player_2_outcome.name

        if bet.market.key == 'totals':
            try:
                scores = event.scores
                points = int(scores[0]['score']) + int(scores[1]['score'])
                bet_points = bet.player_2_outcome.point
                if bet.player_2_outcome.name == 'Over':
                    result = (points > bet_points)
                if bet.player_2_outcome.name == 'Under':
                    result = bet_points > points
            except (ValueError, TypeError, IndexError) as e:
                return False

        if bet.market.key == 'spreads':
            try:
                scores = list(event.scores)
                points_diff = int(scores[0]['score']) - int(scores[1]['score'])
                winner = event.winner

                if bet.player_2_outcome.point < 0:
                    if winner != bet.player_2_outcome.name:
                        return False
                    result = abs(points_diff) >= abs(bet.player_2_outcome.point)
                else:
                    if winner == bet.player_2_outcome.name:
                        result = True
                    result = abs(points_diff) < abs(bet.player_2_outcome.point)
            except (ValueError, TypeError, IndexError) as e:
                return False

        # Store the result
        bet.player_2_outcome_correct = result
        bet.is_player_2_outcome_processed = True
        bet.save()
        return result

    def set_owner_outcome(self, bet, outcome):
        bet.market = outcome.market
        bet.owner_outcome = outcome
        bet.save()

    def set_player_2_outcome(self, bet, outcome):
        bet.player_2_outcome = outcome
        bet.save()

    def set_market(self, bet, market):
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
    owner_outcome_correct = models.BooleanField(default=False)
    player_2_outcome_correct = models.BooleanField(default=False)
    is_owner_outcome_processed = models.BooleanField(default=False)
    is_player_2_outcome_processed = models.BooleanField(default=False)
    is_processed = models.BooleanField(default=False)
    objects = BetManager()
    class Meta:
        db_table = 'core.bet'
