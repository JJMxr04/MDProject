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
    # if instance.id == uuid.UUID("484bc5582bb44ab79a1e942cf8762eda"):
    #     current_timestamp_ny_1 = timezone.now().astimezone(timezone.get_fixed_timezone(-300))
    #     print(f"Updating event- Time:{current_timestamp_ny_1}")
    # Update the associated games when an event is updated
    games = Game.objects.filter(event=instance)
    for game in games:
        match = Match.objects.get_object_by_id(game.match_id)
        game.winner = instance.winner
        game.completed = instance.completed
        game.save()

        if (game == match.player_1_game_1) and (not match.player_1_game_1_completed) :
            match.player_1_game_1_completed = True
        elif (game == match.player_1_game_1) and (match.player_1_game_1_completed):
            continue
        if (game == match.player_1_game_2) and (not match.player_1_game_2_completed ):
            match.player_1_game_2_completed = True
        elif (game == match.player_1_game_2) and (match.player_1_game_2_completed ):
            continue

        if (game == match.player_1_game_3) and not match.player_1_game_3_completed :
            match.player_1_game_3_completed = True

        elif (game == match.player_1_game_3) and match.player_1_game_3_completed :
            continue
        if (game == match.player_1_game_4) and not match.player_1_game_4_completed :
            match.player_1_game_4_completed = True
        elif (game == match.player_1_game_4) and match.player_1_game_4_completed:
            continue
        if (game == match.player_1_game_5) and not match.player_1_game_5_completed :
            match.player_1_game_5_completed = True
        elif (game == match.player_1_game_5) and match.player_1_game_5_completed:
            continue
        if (game == match.player_2_game_1) and not match.player_2_game_1_completed :
            match.player_2_game_1_completed = True
        elif (game == match.player_2_game_1) and match.player_2_game_1_completed :
            continue
        if (game == match.player_2_game_2) and not match.player_2_game_2_completed :
            match.player_2_game_2_completed = True
        elif (game == match.player_2_game_2) and match.player_2_game_2_completed :
            continue
        if (game == match.player_2_game_3) and not match.player_2_game_3_completed :
            match.player_2_game_3_completed = True
        elif (game == match.player_2_game_3) and match.player_2_game_3_completed:
            continue
        if (game == match.player_2_game_4) and not match.player_2_game_4_completed :
            match.player_2_game_4_completed = True
        elif (game == match.player_2_game_4) and match.player_2_game_4_completed :
            continue
        if (game == match.player_2_game_5) and not match.player_2_game_5_completed :
            match.player_2_game_5_completed = True
        elif (game == match.player_2_game_5) and match.player_2_game_5_completed :
            continue
        if (game == match.golden_game) and not match.golden_game_completed :
            match.golden_game_completed = True
        elif (game == match.golden_game) and match.golden_game_completed:
            continue
        if game.owner_choice == game.winner:
            if game.owner == match.player_1:
                if game != match.golden_game:
                    match.player_1_score += 1
                else:
                    match.player_1_score += 2

            if game.owner == match.player_2:
                if game != match.golden_game:
                    match.player_2_score += 1
                else:
                    match.player_2_score += 2
        if game.player_2_choice == game.winner:
            if game.player_2 == match.player_1:
                if game != match.golden_game:
                    match.player_1_score += 1
                else:
                    match.player_2_score += 2
            if game.player_2 == match.player_2:
                if game != match.golden_game:
                    match.player_2_score += 1
                else:
                    match.player_2_score += 2
        if match.golden_game_completed and match.player_1_game_1_completed and match.player_1_game_2_completed and match.player_1_game_3_completed and match.player_1_game_4_completed and match.player_1_game_5_completed and match.player_2_game_1_completed and match.player_2_game_2_completed and  match.player_2_game_3_completed and match.player_2_game_4_completed and match.player_2_game_5_completed:
            if match.player_1_score > match.player_2_score:
                match.winner = match.player_1
            elif match.player_2_score > match.player_1_score:
                match.winner = match.player_2
            elif match.player_1_score == match.player_2_score:
                match.winner = None
            match.match_state = "completed"
        match.save()

    # if instance.id == uuid.UUID("484bc5582bb44ab79a1e942cf8762eda"):
    #     current_timestamp_ny_2 = timezone.now().astimezone(timezone.get_fixed_timezone(-300))
    #     print(f"Finished Updating event- Time:{current_timestamp_ny_2}")
    #     time_difference = current_timestamp_ny_2 - current_timestamp_ny_1
    #     print(f"Time difference:{time_difference}")
