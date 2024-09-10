import uuid
from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.utils import timezone
from core.user.models import User
# from core.event.models import Event
from core.mail.models import Emails
from core.game.models.bet import Bet,Outcome, Event,Market

class GameManager(AbstractManager):
    def create_game(self, owner, player_2, match, event=None, commence_time=None, deadline_time=None, completed=False,
                    home_team=None, away_team=None, winner=None):
        return self.create(owner=owner, player_2=player_2, match_id=match.id, event=event, commence_time=commence_time,
                           deadline_time=deadline_time, completed=completed, home_team=home_team,
                           away_team=away_team, winner=winner,bet=Bet.objects.create_bet())
    
    def get_owner_correctness(self, game):
        bet= game.bet
        event= game.event
        return Bet.objects.calculate_owner_choice(bet,event)
    def get_player_2_correctness(self, game):
        bet= game.bet
        event= game.event
        return Bet.objects.calculate_player_2_choice(bet,event)

    def update_by_id(self, id, current_user, data):
        # print(data)
        print(6)
        game = self.filter(id=id).first()
        new_game = False

        if game is None:

            # If the game does not exist, return false
            return False, False
        print(7)
        if (current_user != game.owner) and (current_user != game.player_2):

            return False, False
        print(8)
        if current_user == game.owner:
            if game.event is None:
                print(8.1)
            new_game = True
            event = Event.objects.get_object_by_id(uuid.UUID(data.get("event_id")))
            if event is None:

                return False, False
                print(8.2)
                commence_time_str = event.commence_time
                print(8.3)
                # Convert the commence_time string to a datetime object
                commence_time = timezone.make_aware(datetime.strptime(commence_time_str, '%Y-%m-%dT%H:%M:%SZ'))
                print(8.4)
                # Check if the commence time is at least 8 hours from now
                current_time = timezone.now()
                print(8.5)
                if commence_time < current_time + timedelta(hours=8):
                    print(8.6)
                    return False, False
                print(8.7)
                game.event = event
                game.home_team = event.home_team
                game.away_team = event.away_team
                game.commence_time = commence_time
                game.deadline_time = commence_time - timedelta(hours=8)
                game.save()
                print(8.8)
        if current_user == game.player_2 and game.bet.owner_outcome is None:
            return False, False
        print(9)
        # Check if the event has already started
        current_time = timezone.now()
        # print('check 8')
        if game.commence_time and game.commence_time <= current_time:
            return False, False
        print(10)
        if data.get("player_choice"):
            player_choice = data.get("player_choice")
            print(10.1)
            print(player_choice)
            outcome=Outcome.objects.filter(id=player_choice).first()
            print("10.1.1")
            if Outcome is None and current_user != game.owner:
                print("10.1.2")
                return False, False
            print(10.2)
            if Outcome is None and current_user == game.owner:
                Bet.objects.set_market(game.bet,outcome.market)
            print(10.3)
            game = self.filter(id=id).first()

            print("10.3.1")
            print(10.4)
            if current_user == game.owner:
                if game.bet.owner_outcome is None:
                    Bet.objects.set_owner_outcome(game.bet,outcome)

            print(10.5)
            if current_user == game.player_2:
                if game.bet.player_2_outcome is None:
                    Bet.objects.set_player_2_outcome(game.bet,outcome)
        print(11)

        game.save()
        print(12)
        # Email
        if current_user == game.owner:
            Emails.send_opponent_pick_notification(game.player_2,game.owner.username)
        if current_user == game.player_2:
            Emails.send_opponent_pick_notification(game.owner,game.player_2.username)
        print(13)
        # print('check 15')

        return new_game, game

    def get_golden_game(self, player_1, player_2, match):
        event = Event.objects.get_random_golden()
        return Game.objects.create_game(player_1, player_2, match, event, event.commence_time, None, event.completed,
                                        event.home_team, event.away_team)

    def game_event_update(self, game, instance):
        game.winner = instance.winner
        game.completed = instance.completed
        game.save()


class Game(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owner_game')
    player_2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='player_2_game')
    match_id = models.CharField(max_length=200, default='0', null=False, blank=False)
    commence_time = models.DateTimeField(default=None, null=True, blank=True)
    deadline_time = models.DateTimeField(default=None, null=True, blank=True)
    completed = models.BooleanField(default=False)
    home_team = models.CharField(max_length=200, default=None, null=True, blank=True)
    away_team = models.CharField(max_length=200, default=None, null=True, blank=True)
    winner = models.CharField(max_length=200, default=None, null=True, blank=True)
    owner_choice = models.CharField(max_length=200, default=None, null=True, blank=True)
    player_2_choice = models.CharField(max_length=200, default=None, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='games', null=True, blank=True)
    bet = models.ForeignKey(Bet, on_delete=models.CASCADE, related_name='game_bet', null=True, blank=True)
    objects = GameManager()

    class Meta:
        db_table = 'core.game'
