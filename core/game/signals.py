from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models import Event
from core.game.models import Game


@receiver(post_save, sender=Event)
def update_games_on_event_update(sender, instance, **kwargs):
    print("working")
    # Update the associated games when an event is updated
    games = Game.objects.filter(event=instance)
    for game in games:
        game.winner = instance.winner
        game.completed = instance.completed
        game.save()