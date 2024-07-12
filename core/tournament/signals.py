import time

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.match.models import Match
from core.tournament.models.tournament import Round
from core.event.serializers.event import EventSerializer
from core.event.models import Event
from core.game.models import Game
from core.game.serializers import GameSerializer
from django.utils import timezone
import uuid
from core.mail.models import Emails


@receiver(post_save, sender=Match)
def update_round_match(sender, instance, **kwargs):
    match = instance
    if match.match_state != "completed":
        return
    round = Round.objects.get_round_by_match(match=match)

    round.completed = True

    if match.winner == round.player_1.player:
        round.winner = round.player_1
    if match.winner == round.player_2.player:
        round.winner = round.player_2

    round.save()
    if round.level_num == 0:
        # print(f'Level 0')
        round.tournament.winner = round.winner
        round.tournament.state = 'completed'
        round.tournament.save()
        tournament = round.tournament
        winner = round.tournament.winner.player
        #Email
        Emails.send_tournament_victory_notification(winner,tournament)
        return

    next_round = round.next_round
    if round == next_round.prev_round_1:
        next_round.player_1 = round.winner
    if round == next_round.prev_round_2:
        next_round.player_2 = round.winner
    round.save()
    next_round.save()
    next_round=round.next_round
    if (next_round.player_1 ) and (next_round.player_2 ):

        # time.sleep(2)
        # print(Event.objects.filter(completed=False))
        next_round.match = Match.objects.create_match(next_round.player_1.player,next_round.player_2.player)
        # print(f"Golden Game Event for round {next_round.level_num}:{next_round.match.golden_game.event}")
        next_round.save()
