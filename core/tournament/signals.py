from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.match.models import Match
from core.tournament.models.tournament import Round
from django.utils import timezone
import uuid


# @receiver(post_save, sender=Match)
# def update_round_match(sender, instance, **kwargs):
#     match = instance
#     round =  Round.objects.filter(match=match.id)
#     print(round)
#     if match.match_state != 'completed':
#         return
#
#     round.completed = True
#
#     if match.winner == round.player_1.player:
#         winner = round.player_1
#     if match.winner == round.player_2.player:
#         winner = round.player_2
#         round.winner = winner
#
#     round.save()
#     if round.level_num == 0:
#         round.tournament.winner = winner
#         round.tournament.state = 'completed'
#         round.tournament.save()
#         return
#
#     next_round = round.next_round
#     if round == next_round.prev_round_1:
#         player_1 = round.winner
#     if round == next_round.prev_round_2:
#         player_2 = round.winner
#
#     if (next_round.player_1 is not None) and (next_round.player_2 is not None):
#         next_round.match = Match.objects.create_match(next_round.player_1.player,next_round.player_2.player)
#         next_round.save()
