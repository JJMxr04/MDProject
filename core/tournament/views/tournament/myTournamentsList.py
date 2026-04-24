from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from core.tournament.models import Tournament


@login_required(login_url='/auth/login/')
def my_tournaments(request):
    selected_state = request.GET.get('state', '')
    search_query = request.GET.get('query', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    page = request.GET.get('page', 1)

    tournaments = Tournament.objects.all().annotate(
        accepted_count=Count('player', distinct=True),
        rounds_total=Count('rounds', distinct=True),
        rounds_completed=Count('rounds', filter=Q(rounds__completed=True), distinct=True),
    ).order_by('-start_date')

    if search_query:
        tournaments = tournaments.filter(name__icontains=search_query)
    if selected_state:
        tournaments = tournaments.filter(state=selected_state)
    if start_date:
        tournaments = tournaments.filter(start_date__gte=start_date)
    if end_date:
        tournaments = tournaments.filter(start_date__lte=end_date)

    paginator = Paginator(tournaments, 12)
    paginated_tournaments = paginator.get_page(page)

    quick_filters = [
        {"label": "All",         "value": "",          "is_active": selected_state == ""},
        {"label": "Upcoming",    "value": "created",   "is_active": selected_state == "created"},
        {"label": "In Progress", "value": "inprogress","is_active": selected_state == "inprogress"},
        {"label": "Completed",   "value": "completed", "is_active": selected_state == "completed"},
        {"label": "Aborted",     "value": "aborted",   "is_active": selected_state == "aborted"},
    ]

    context = {
        'tournaments': paginated_tournaments,
        'selected_state': selected_state,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
        'quick_filters': quick_filters,
    }

    return render(request, 'portal/tournament/my_tournaments.html', context)
