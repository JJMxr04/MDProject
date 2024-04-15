import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from core.user.models import User

class TournamentManager(AbstractManager):

    def create(self,name,start_date,max_accepted_players):
        end_date = self.get_end_date()
        return self.create(name=name,start_date=start_date,end_data=None,state="")

    pass

    def get_end_date(date):
        # Calculate the next Sunday
        days = (6 - date.weekday() + 7) % 7
        next_week_day = date + timedelta(days=days)

        # Set the time to 11:59 PM
        next_week_day = next_week_day.replace(hour=23, minute=59, second=0, microsecond=0)

        # Add a week to the date
        end_date = next_week_day + timedelta(weeks=1)

        return end_date

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


class Tournament(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField(auto_now_add=False)
    end_date = models.DateTimeField(auto_now_add=False)
    state = models.CharField(max_length=10, default='created', null=False, blank=False)
    max_accepted_players = models.IntegerField(null=False, blank=False)
    invited_players = models.ManyToManyField(User, related_name='invited_to_tournaments', through='InvitedPlayer')
    players = models.ManyToManyField(User, related_name='participating_in_tournaments', through='Player')

    objects = TournamentManager()

    class Meta:
        db_table = 'core_tournament'

    def __str__(self):
        return self.name

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