from django.shortcuts import render, get_object_or_404
from core.tournament.models import Tournament
from core.tournament.models.tournament import Round
from django.utils.timezone import now
from itertools import groupby
from operator import attrgetter

def my_tournament_detail(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    rounds = tournament.rounds.all().order_by('level_num')

    grouped_rounds = {level: list(rounds) for level, rounds in groupby(rounds, key=attrgetter('level_num'))}

    context = {
        'tournament': tournament,
        'grouped_rounds': grouped_rounds,
    }
    return render(request, 'portal/tournament/my_tournament_detail.html', context)
