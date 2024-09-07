import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from core.user.models import User
from core.event.models import Event
from core.game.models import Game
from core.mail.models import Emails
from core.match.models.TieBreaker import TieBreaker
from datetime import datetime
import uuid
from rest_framework.response import Response


class MatchManager(AbstractManager):
    def create_match(self, player_1, player_2=None, start_date = timezone.now()):
        start_date = timezone.now()
        end_date = start_date + timedelta(weeks=1)

        if player_2 is None:
            return self.create(player_1=player_1, player_2=player_2, start_date=start_date, end_date=end_date)
        else:
            match = self.create(player_1=player_1, player_2=player_2, start_date=start_date, end_date=end_date)
            return self.accept_match(match, player_2)


    def calculate_winner(self, match):
        if match.player_1_score > match.player_2_score:
            match.winner = match.player_1
        elif match.player_2_score > match.player_1_score:
            match.winner = match.player_2
        elif match.player_1_score == match.player_2_score:
            match.tiebreaker = TieBreaker.objects.create()
            match.winner = TieBreaker.objects.calculate_winner(match.tiebreaker,match.player_1,match.player_2)
        match.match_state = "completed"
        match.save()

        if match.winner == match.player_1:
            Emails.send_match_victory_notification(match.player_1, match.player_2.username)
            Emails.send_match_lost_notification(match.player_2, match.player_1.username)
        elif match.winner == match.player_2:
            Emails.send_match_victory_notification(match.player_2, match.player_1.username)
            Emails.send_match_lost_notification(match.player_1, match.player_2.username)
        # else:
        #     Emails.send_match_tie_notification(match.player_1, match.player_2.username)
        #     Emails.send_match_tie_notification(match.player_2, match.player_1.username)


    def accept_match(self, match, player_2):
        match = self.get_object_by_id(id=match.id)
        if match is None:
            return None
        match.match_state = "accepted"
        match.player_2 = player_2
        match.player_1_game_1 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_1_game_2 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_1_game_3 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_1_game_4 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_1_game_5 = Game.objects.create_game(match.player_1, match.player_2, match)

        match.player_2_game_1 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_2_game_2 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_2_game_3 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_2_game_4 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_2_game_5 = Game.objects.create_game(match.player_1, match.player_2, match)
        match.player_2_game_1 = Game.objects.create_game(match.player_2,match.player_1, match)
        match.player_2_game_2 = Game.objects.create_game(match.player_2, match.player_1, match)
        match.player_2_game_3 = Game.objects.create_game(match.player_2, match.player_1, match)
        match.player_2_game_4 = Game.objects.create_game(match.player_2, match.player_1, match)
        match.player_2_game_5 = Game.objects.create_game(match.player_2, match.player_1, match)


        match.golden_game = Game.objects.get_golden_game(match.player_1, match.player_2, match)
        match.save()

        return match

    def match_game_event_update(self, games, instance):
        for game in games:
            match = Match.objects.get_object_by_id(game.match_id)
            Game.objects.game_event_update(game=game, instance=instance)

            if (game == match.player_1_game_1) and (not match.player_1_game_1_completed):
                match.player_1_game_1_completed = True
            if (game == match.player_1_game_2) and (not match.player_1_game_2_completed):
                match.player_1_game_2_completed = True

            if (game == match.player_1_game_3) and not match.player_1_game_3_completed:
                match.player_1_game_3_completed = True
            if (game == match.player_1_game_4) and not match.player_1_game_4_completed:
                match.player_1_game_4_completed = True
            if (game == match.player_1_game_5) and not match.player_1_game_5_completed:
                match.player_1_game_5_completed = True
            if (game == match.player_2_game_1) and not match.player_2_game_1_completed:
                match.player_2_game_1_completed = True
            if (game == match.player_2_game_2) and not match.player_2_game_2_completed:
                match.player_2_game_2_completed = True
            if (game == match.player_2_game_3) and not match.player_2_game_3_completed:
                match.player_2_game_3_completed = True
            if (game == match.player_2_game_4) and not match.player_2_game_4_completed:
                match.player_2_game_4_completed = True
            if (game == match.player_2_game_5) and not match.player_2_game_5_completed:
                match.player_2_game_5_completed = True
            if (game == match.golden_game) and not match.golden_game_completed:
                match.golden_game_completed = True
            if (game == match.golden_game):
                if Game.objects.get_owner_correctness(game):
                    match.player_1_score += 2
                if Game.objects.get_player_2_correctness(game):
                    match.player_2_score += 2
            else:
                if Game.objects.get_owner_correctness(game):
                    match.player_1_score += 1
                if Game.objects.get_player_2_correctness(game):
                    match.player_2_score += 1
            match.save()
            if match.golden_game_completed and match.player_1_game_1_completed and match.player_1_game_2_completed and match.player_1_game_3_completed and match.player_1_game_4_completed and match.player_1_game_5_completed and match.player_2_game_1_completed and match.player_2_game_2_completed and match.player_2_game_3_completed and match.player_2_game_4_completed and match.player_2_game_5_completed:
                self.calcutate_winner(match)

    def upload_pick(self, player, match, data):

        if (match.player_1 != player) and (match.player_2 != player):
            return Response({'error': "Either you are not a participant of this match or You already uploaded your games"}, status=400)

        eventList = []

        if match.golden_game.event !=None:
            eventList.append(match.golden_game.event.id)
        if match.player_1_game_1.event !=None:
            eventList.append(match.player_1_game_1.event.id)
        if match.player_1_game_2.event !=None:
            eventList.append(match.player_1_game_2.event.id)
        if match.player_1_game_3.event !=None:
            eventList.append(match.player_1_game_3.event.id)
        if match.player_1_game_4.event !=None:
            eventList.append(match.player_1_game_4.event.id)
        if match.player_1_game_5.event !=None:
            eventList.append(match.player_1_game_5.event.id)
        if match.player_2_game_1.event !=None:
            eventList.append(match.player_2_game_1.event.id)
        if match.player_2_game_2.event !=None:
            eventList.append(match.player_2_game_2.event.id)
        if match.player_2_game_3.event !=None:
            eventList.append(match.player_2_game_3.event.id)
        if match.player_2_game_4.event !=None:
            eventList.append(match.player_2_game_4.event.id)
        if match.player_2_game_5.event !=None:
            eventList.append(match.player_2_game_5.event.id)
        if uuid.UUID(data.get("event_id")) in eventList:
            return Response(
                {'error': "This game is already been selected"},
                status=400)

        if match.player_1 == player:
            if match.player_1_game_1.event == None:
                Game.objects.update_by_id(match.player_1_game_1.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_2.event == None:
                Game.objects.update_by_id(match.player_1_game_2.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_3.event == None:
                Game.objects.update_by_id(match.player_1_game_3.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_4.event == None:
                Game.objects.update_by_id(match.player_1_game_4.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_1_game_5.event == None:
                Game.objects.update_by_id(match.player_1_game_5.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
        if match.player_2 == player:
            if match.player_2_game_1.event == None:
                Game.objects.update_by_id(match.player_2_game_1.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_2.event == None:
                Game.objects.update_by_id(match.player_2_game_2.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_3.event == None:
                Game.objects.update_by_id(match.player_2_game_3.id,player,data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_4.event == None:
                Game.objects.update_by_id(match.player_2_game_4.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
            if match.player_2_game_5.event == None:
                Game.objects.update_by_id(match.player_2_game_5.id, player, data)
                return Response({'message': 'Request was successful'}, status=200)
        return Response({'error': "Either you are not a participant of this match or You already uploaded your games"}, status=400)



class Match(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_1_match')

    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_match', null=True, default=None)
    winner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='winner_match', null=True, default=None)

    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_match',null=True,default=None)
    winner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='winner_match',null=True,default=None)
    match_state = models.CharField(max_length=10, default='created', null=False, blank=False) #created, completed

    match_type = models.CharField(max_length=10, default='public', null=False, blank=False)
    tiebreaker = models.ForeignKey(TieBreaker, on_delete=models.CASCADE, related_name='match_tiebreaker', null=True, blank=True, default=None)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True, default=None)
    player_1_score = models.IntegerField(default=0, null=False, blank=False)
    player_2_score = models.IntegerField(default=0, null=False, blank=False)

    player_1_game_1 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_1',
                                        blank=False, null=True, default=None)
    player_1_game_1_completed = models.BooleanField(default=False)
    player_1_game_2 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_2',
                                        blank=False, null=True, default=None)
    player_1_game_2_completed = models.BooleanField(default=False)
    player_1_game_3 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_3',
                                        blank=False, null=True, default=None)
    player_1_game_3_completed = models.BooleanField(default=False)
    player_1_game_4 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_4',
                                        blank=False, null=True, default=None)
    player_1_game_4_completed = models.BooleanField(default=False)
    player_1_game_5 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_1_game_5',
                                        blank=False, null=True, default=None)
    player_1_game_5_completed = models.BooleanField(default=False)

    player_2_game_1 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_1',
                                        blank=False, null=True, default=None)
    player_2_game_1_completed = models.BooleanField(default=False)
    player_2_game_2 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_2',
                                        blank=False, null=True, default=None)
    player_2_game_2_completed = models.BooleanField(default=False)
    player_2_game_3 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_3',
                                        blank=False, null=True, default=None)
    player_2_game_3_completed = models.BooleanField(default=False)
    player_2_game_4 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_4',
                                        blank=False, null=True, default=None)
    player_2_game_4_completed = models.BooleanField(default=False)
    player_2_game_5 = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='match_player_2_game_5',
                                        blank=False, null=True, default=None)
    player_2_game_5_completed = models.BooleanField(default=False)

    golden_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='golden_game', blank=False, null=True,
                                    default=None)
    golden_game_completed = models.BooleanField(default=False)

    objects = MatchManager()

    class meta:
        db_table = "'core.match'"



    def __str__(self):
        return f'{self.player_1} vs {self.player_2} '

