from datetime import timedelta
from django.utils import timezone
from core.tournament.models.tournament import Round, Tournament, Player, InvitePlayer

from core.mail.models import Emails

class Tournament2DayReminder():

    def get_upcoming_tournaments(self):
        now = timezone.now()
        one_day_from_now = now + timedelta(days=2)
        tournaments = Tournament.objects.filter(state='created', start_date__date=one_day_from_now.date())
        return tournaments

    def send_players_Email(self,tournament):
        players = Player.objects.filter(tournament=tournament)

        for player in players:
            Emails.send_tournament_starting_notification(player,tournament)

    def get_tournments_send_player_email(self):
        tournaments = self.get_upcoming_tournaments()

        for tournament in tournaments:
            self.send_players_Email(tournament)

