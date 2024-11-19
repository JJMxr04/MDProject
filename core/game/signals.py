from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models import Event
from core.game.models import Game
from core.match.models import Match
from django.utils import timezone
import uuid


@receiver(post_save, sender=Event)
def update_games_on_event_update(sender, instance, **kwargs):
    if  not instance.completed:
        return 
    games = Game.objects.filter(event=instance,completed=False)
    Match.objects.match_game_event_update(games=games,instance=instance)
