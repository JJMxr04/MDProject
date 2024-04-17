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
        end_date = self.get_end_date(start_date)
        tournament = self.model(name=name, start_date=start_date, end_date=end_date, max_accepted_players=max_accepted_players)
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
    def create_rounds(self, tournament):
        # Calculate the number of levels
        levels = tournament.levels

        # Create the top level round (level 0) containing one match
        top_level_round = Round.objects.create(tournament=tournament, level_num=0)

        # Recursively create rounds for each level from 0 to levels - 1
        self._create_rounds_recursive(tournament, top_level_round, levels - 1)

    def _create_rounds_recursive(self, tournament, parent_round, remaining_levels):
        if remaining_levels <= 0:
            return

        # Calculate the number of rounds in this level
        num_rounds = int(tournament.max_accepted_players / 2)

        for i in range(num_rounds):
            # Create a new round
            round_num = parent_round.level_num + 1
            new_round = Round.objects.create(tournament=tournament, level_num=round_num, prev_round_1=parent_round)

            # Recursively create rounds for the next level
            self._create_rounds_recursive(tournament, new_round, remaining_levels - 1)


class RoundManager(AbstractManager):
    pass


class Tournament(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField(auto_now_add=False)
    end_date = models.DateTimeField(auto_now_add=False)
    state = models.CharField(max_length=10, default='created', null=False, blank=False)
    max_accepted_players = models.IntegerField(null=False, blank=False)
    invited_players = models.ManyToManyField(User, related_name='invited_to_tournaments', through='InvitedPlayer')
    players = models.ManyToManyField(User, related_name='participating_in_tournaments', through='Player')
    levels = models.FloatField(default=0)  # Field to store tournament levels
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='won_tournaments', null=True, blank=True)

    objects = TournamentManager()

    class Meta:
        db_table = 'core_tournament'

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
    next_match = models.OneToOneField(Match, related_name='next_match_for_round', on_delete=models.SET_NULL, blank=True, null=True)
    match_1 = models.ForeignKey(Match, related_name='round_match_1', on_delete=models.SET_NULL, blank=True, null=True)
    match_2 = models.ForeignKey(Match, related_name='round_match_2', on_delete=models.SET_NULL, blank=True, null=True)
    next_round = models.ForeignKey('self', related_name='next_rounds_from_prev_round', on_delete=models.SET_NULL, blank=True, null=True)
    prev_round_1 = models.ForeignKey('self', related_name='prev_round_1_to_next_rounds', on_delete=models.SET_NULL, blank=True, null=True)
    prev_round_2 = models.ForeignKey('self', related_name='prev_round_2_to_next_rounds', on_delete=models.SET_NULL, blank=True, null=True)
    completed = models.BooleanField(default=False)

    objects = RoundManager()

    class Meta:
        db_table = 'core_round'

    def __str__(self):
        return f"Round {self.level_num} of {self.tournament}"
