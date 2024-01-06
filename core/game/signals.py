from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models import Event
from core.game.models import Game
from django.utils import timezone
import uuid


@receiver(post_save, sender=Event)
def update_games_on_event_update(sender, instance, **kwargs):
    if instance.id == uuid.UUID("484bc5582bb44ab79a1e942cf8762eda"):
        current_timestamp_ny_1 = timezone.now().astimezone(timezone.get_fixed_timezone(-300))
        print(f"Updating event- Time:{current_timestamp_ny_1}")
    # Update the associated games when an event is updated
    games = Game.objects.filter(event=instance)
    for game in games:
        game.winner = instance.winner
        game.completed = instance.completed
        game.save()

    if instance.id == uuid.UUID("484bc5582bb44ab79a1e942cf8762eda"):
        current_timestamp_ny_2 = timezone.now().astimezone(timezone.get_fixed_timezone(-300))
        print(f"Finished Updating event- Time:{current_timestamp_ny_2}")
        time_difference = current_timestamp_ny_2 - current_timestamp_ny_1
        print(f"Time difference:{time_difference}")

