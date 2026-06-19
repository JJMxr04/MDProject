from datetime import timedelta

from django.utils import timezone

from core.mail.models import Emails
from core.tournament.models.tournament import InvitedPlayer, Player, Round, Tournament


class Tournament2DayReminder():

    def get_upcoming_tournaments(self):
        now = timezone.now()
        one_day_from_now = now + timedelta(days=2)
        tournaments = Tournament.objects.filter(state='created', start_date__date=one_day_from_now.date())
        return tournaments

    def send_players_Email(self,tournament):
        players = Player.objects.filter(tournament=tournament).select_related('player')

        for player in players:
            # Player is the tournament join row; the User lives on .player.
            Emails.send_tournament_starting_notification(player.player, tournament)

    def get_tournments_send_player_email(self):
        tournaments = self.get_upcoming_tournaments()

        for tournament in tournaments:
            self.send_players_Email(tournament)

