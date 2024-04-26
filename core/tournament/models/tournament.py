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

    def get_invited_player(self,tournament):
        return InvitedPlayer.objects.get_Invited_Players(tournament=tournament)

    def get_players(self,tournament):
        return Player.objects.get_Players(tournament=tournament)

    def acceptInvite(self, tourney_id, user_email):
        try:
            tournament = self.get(pk=tourney_id)
            if not tournament:
                print(f"Tournament with ID {tourney_id} not found.")
                return False

            user = User.objects.get(email=user_email)

            if not InvitedPlayer.objects.check_invited_player(tournament,user):
                print("User was not invited to this tournament")
                return False
            if tournament.state != 'created':
                return False
            players = list(Player.objects.get_Players(tournament=tournament))
            if len(players) == tournament.max_accepted_players:
                return False
            if Player.objects.check_player_participating(tournament=tournament,user=user):
                return False
            #
            player = Player.objects.create_player(tournament,user)
            return True

        except ObjectDoesNotExist as e:
            print(f"Object not found: {e}")
            return False
        except AttributeError as e:
            print(f"Attribute error: {e}")
            return False

    def invitePlayer(self, tourney_id, user_email):
        try:
            tournament = self.get(pk=tourney_id)
            if not tournament:
                print(f"Tournament with ID {tourney_id} not found.")
                return False

            # Try to get the user, handle the exception if not found
            try:
                user = User.objects.get(email=user_email)
            except ObjectDoesNotExist:
                print(f"User with email {user_email} does not exist.")
                return False

            # Check if the user is already participating in the tournament or has been invited

            if InvitedPlayer.objects.check_invited_player(tournament,user):
                print("User is already invited or part of the tournament.")
                return False

            # Add the user to the invited players list
            InvitedPlayer.objects.create(tournament=tournament, player=user)
            return True

        except ObjectDoesNotExist as e:
            print(f"Object not found: {e}")
            return False
        except AttributeError as e:
            print(f"Attribute error: {e}")
            return False

    def make_init_matches(self,tournament):
        botton_level_rounds = Round.objects.filter(tournament=tournament,level_num=(tournament.levels -1))
        players = list(Player.objects.get_Players(tournament=tournament))
        # print(len(players))
        for round in botton_level_rounds:
            # if(len(players) ==1 ):
            #     print("poop")
            player_1 = players.pop()
            player_2 = players.pop()
            Round.objects.assign_players(round=round,player_1=player_1,player_2=player_2)
            Round.objects.create_tournament_match(round)




    # @transaction.atomic
    def create_rounds(self,tournament):
        tournament.state = 'inprogress'
        final_round = Round.objects.create_bracket(tournament)
        tournament.final_round = final_round
        tournament.save()




class RoundManager(AbstractManager):
    def create_bracket(self, tournament, current_level=0, next_round=None):
        if current_level >= tournament.levels:
            return None

        # Create and save the current round
        current_round = Round.objects.create(
            tournament=tournament,
            level_num=current_level,
            next_round=next_round,
        )

        # Recursively create and assign the previous rounds
        previous_round_1 = self.create_bracket(tournament, current_level + 1, current_round)
        previous_round_2 = self.create_bracket(tournament, current_level + 1, current_round)

        # Assign the previous rounds and save
        current_round.prev_round_1 = previous_round_1
        current_round.prev_round_2 = previous_round_2
        current_round.save()  # Ensure relationships are persisted

        return current_round

    def create_tournament_match(self,round):
        round.match = Match.objects.create_match(round.player_1.player,round.player_2.player)
        round.save()

    def assign_players(self,round,player_1=None,player_2=None):
        if ((round.player_1 == None) and (player_1 != None) ):
            round.player_1 = player_1
        if ((round.player_2 == None) and (player_2 != None) ):
            round.player_2 = player_2
        round.save()

    def get_tourney_level_rounds(self,tournament, level):
        return self.filter(tournament=tournament,level_num=level)


    def get_round_by_match(self,match):
        return self.filter(match=match).first()




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

    def check_invited_player(self,tourney,user):
        try:
            invite = self.get(tournament=tourney,player=user)
            return True
        except ObjectDoesNotExist as e:
            # print(1)
            # print(f"Object not found: {e}")
            return False

    def get_Invited_Players(self,tournament):
        return self.filter(tournament=tournament)

class PlayerManager(AbstractManager):
    def create_player(self, tournament, player, seed=None):
        return self.create(tournament=tournament, player=player, seed=seed)

    def update_player(self, player, **kwargs):
        for key, value in kwargs.items():
            setattr(player, key, value)
        player.save()
        return player

    def delete_player(self, player):
        player.delete()

    def get_Players(self,tournament):
        return self.filter(tournament=tournament)

    def check_player_participating(self,tournament, user):
        try:
            player = self.get(tournament=tournament,player=user)
            return True
        except ObjectDoesNotExist as e:
            return False


class Tournament(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    state = models.CharField(max_length=10, default='created') # created, inprogress, completed
    max_accepted_players = models.IntegerField()
    levels = models.FloatField(default=0)
    winner = models.ForeignKey('Player', on_delete=models.SET_NULL, related_name='won_tournaments', null=True,
                               blank=True)
    final_round = models.ForeignKey('Round', on_delete=models.CASCADE, related_name='tournament_final_round', null=True,
                                    blank=True)

    objects = TournamentManager()

    class Meta:
        db_table = 'core_tournament'

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
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)  # Linking to Tournament
    player = models.ForeignKey(User, on_delete=models.CASCADE)  # Linking to User
    accepted = models.BooleanField(default=False)
    accepted_date = models.DateTimeField(null=True)
    invited_date = models.DateTimeField(null=True)
    objects = InvitedPlayerManager()

class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)  # Linking to Tournament
    player = models.ForeignKey(User, on_delete=models.CASCADE)  # Linking to User
    seed = models.IntegerField(null=True)
    division = models.IntegerField(blank=True, null=True)
    objects = PlayerManager()

