from datetime import timedelta
from django.utils import timezone
from core.tournament.models.tournament import Round, Tournament, Player, InvitedPlayer

class BracketMaker():

    def get_upcoming_tournaments(self):
        now = timezone.now()
        one_day_from_now = now + timedelta(days=1)
        tournaments = Tournament.objects.filter(state='created', start_date__date=one_day_from_now.date())
        return tournaments

    def create_brackets(self):
        tournaments = self.get_upcoming_tournaments()

        for tournament in tournaments:
            Tournament.objects.bracket_maker(tournament)

