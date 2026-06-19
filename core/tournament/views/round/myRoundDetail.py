from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.tournament.models.tournament import Round


@login_required(login_url='/auth/login/')
def my_round_detail_view(request, round_id):
    round_details = get_object_or_404(Round, id=round_id)

    context = {
        'round_details': round_details,
    }
    return render(request, 'portal/round/my_round_detail.html', context)
