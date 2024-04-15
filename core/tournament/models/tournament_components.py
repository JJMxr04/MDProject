import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from core.user.models import User
from core.tournament.models.tournament import Tournament





class InvitedPlayerManager(AbstractManager):
    def create_invited_player(self, tournament, player, accepted=False, accepted_date=None, invited_date=None):
        return self.create(tournament=tournament, player=player, accepted=accepted, accepted_date=accepted_date, invited_date=invited_date)

    def update_invited_player(self, invited_player, **kwargs):
        for key, value in kwargs.items():
            setattr(invited_player, key, value)
        invited_player.save()
        return invited_player

    def delete_invited_player(self, invited_player):
        invited_player.delete()

class PlayerManager(AbstractManager):
    def create_player(self, tournament, player, seed):
        return self.create(tournament=tournament, player=player, seed=seed)

    def update_player(self, player, **kwargs):
        for key, value in kwargs.items():
            setattr(player, key, value)
        player.save()
        return player

    def delete_player(self, player):
        player.delete()





class InvitedPlayer(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    accepted_date = models.DateTimeField()
    invited_date = models.DateTimeField()
    objects = InvitedPlayerManager()

class Player(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    seed = models.IntegerField()
    objects = PlayerManager()