import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.utils import timezone
from core.user.models import User
from core.match.models.match import Match

import math
from django.db import transaction

class TournamentManager(AbstractManager):

    def create(self, name, start_date, max_accepted_players):
        start_date_aware = timezone.make_aware(start_date)
        levels = self.get_tourny_level(max_accepted_players)
        end_date = self.get_end_date(start_date_aware, levels)  # Pass the aware start_date
        tournament = self.model(name=name, start_date=start_date_aware, end_date=end_date, max_accepted_players=max_accepted_players, levels=levels)
        tournament.save()
        return tournament

    def get_end_date(self, date, num_weeks):
        # Calculate the next Sunday
        days_until_sunday = (6 - date.weekday() + 7) % 7
        next_sunday = date + timedelta(days=days_until_sunday)

        # Set the time to midnight
        end_date = next_sunday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Add the specified number of weeks (levels) to the date
        end_date += timedelta(weeks=num_weeks)

        return end_date

    def get_tourny_level(self, num):
        return math.log2(num)

    def acceptInvite(self, tourney_id, user_email):
        try:
            tournament = self.get(pk=tourney_id)
            user = User.objects.get(email=user_email)
            # Check if the user has been invited to the tournament
            if tournament.invited_players.filter(pk=user.pk).exists():
                # Add the user to the players participating in the tournament
                tournament.players.add(user)
                # Remove the user from the invited players list
                tournament.invited_players.remove(user)
                return True  # Successfully accepted the invitation
            else:
                return False  # User has not been invited to the tournament
        except ObjectDoesNotExist:
            return False  # Tournament or User does not exist

    def invitePlayer(self, tourney_id, user_email):
        try:
            tournament = self.get(pk=tourney_id)
            user = User.objects.get(email=user_email)
            # Check if the user is already participating in the tournament or has been invited
            if tournament.players.filter(pk=user.pk).exists() or tournament.invited_players.filter(pk=user.pk).exists():
                return False  # User is already participating in the tournament or has been invited
            else:
                # Add the user to the invited players list
                tournament.invited_players.add(user)
                return True  # Successfully invited the player
        except ObjectDoesNotExist:
            return False  # Tournament or User does not exist



    @transaction.atomic
    def create_rounds(self,tournament):
        Round.objects.create_bracket(tournament)





class RoundManager(AbstractManager):
    def create_bracket(self, tournament, current_level = 0,next_round=None):
        print(f"Remaining levels: {current_level}")
        if current_level == tournament.levels:
            return None
        round = Round.objects.create(tournament=tournament, level_num=current_level,next_round=next_round)
        round.previous_round_1 =self.create_bracket(tournament,current_level+1,round)
        round.previous_round_2 = self.create_bracket(tournament,current_level+1,round)

        return round
    pass

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
    levels = models.FloatField(default=0)  # Field to store tournament levels
    winner = models.ForeignKey('Player', on_delete=models.SET_NULL, related_name='won_tournaments', null=True, blank=True)

    # Define one-to-many relationships with InvitedPlayer and Player
    invited_players = models.ForeignKey('InvitedPlayer', on_delete=models.CASCADE, related_name='tournament_invited_players', null=True, blank=True)
    players = models.ForeignKey('Player', on_delete=models.CASCADE, related_name='tournament_players', null=True, blank=True)

    objects = TournamentManager()

    class Meta:
        db_table = 'core_tournament'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Calculate levels when saving
        self.levels = self.__class__.objects.get_tourny_level(self.max_accepted_players)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Calculate levels when saving
        self.levels = self.__class__.objects.get_tourny_level(self.max_accepted_players)
        super().save(*args, **kwargs)


class Round(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='rounds')
    level_num = models.IntegerField()
    match = models.ForeignKey(Match, related_name='round_match', on_delete=models.SET_NULL, blank=True, null=True)
    next_round = models.ForeignKey('self', related_name='next_rounds_from_prev_round', on_delete=models.SET_NULL, blank=True, null=True)
    prev_round_1 = models.ForeignKey('self', related_name='prev_round_1_to_next_rounds', on_delete=models.SET_NULL, blank=True, null=True)
    prev_round_2 = models.ForeignKey('self', related_name='prev_round_2_to_next_rounds', on_delete=models.SET_NULL, blank=True, null=True)

    player_1 = models.ForeignKey('Player', related_name='round_player_1', on_delete=models.SET_NULL,
                                     blank=True, null=True)
    player_2 = models.ForeignKey('Player', related_name='round_player_2', on_delete=models.SET_NULL,
                                 blank=True, null=True)
    winner = models.ForeignKey('Player', related_name='round_winner', on_delete=models.SET_NULL,
                                 blank=True, null=True)
    completed = models.BooleanField(default=False)


    objects = RoundManager()

    class Meta:
        db_table = 'core_round'

    def __str__(self):
        if(self.player_1 and self.player_2):
            return f"Round {self.level_num} of {self.tournament}: {self.player_1.player.name} VS {self.player_2.player.name}"

        if(self.player_1 and not self.player_2):
            return f"Round {self.level_num} of {self.tournament}: {self.player_1.player.name} VS TBD"

        if(self.player_2 and not self.player_1):
            return f"Round {self.level_num} of {self.tournament}: TBD VS {self.player_2.player.name}"
        return f"Round {self.level_num} of {self.tournament}: TBD Vs TBD"


class InvitedPlayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    accepted_date = models.DateTimeField()
    invited_date = models.DateTimeField()
    objects = InvitedPlayerManager()

class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    player = models.ForeignKey(User, on_delete=models.CASCADE)
    seed = models.IntegerField()
    division = models.IntegerField(blank=True, null=True)
    objects = PlayerManager()