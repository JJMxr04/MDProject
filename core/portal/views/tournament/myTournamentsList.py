from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from core.tournament.models import Tournament
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
@login_required(login_url='/auth/login/')
def my_tournaments(request):
    # Fetch query parameters
    selected_state = request.GET.get('state', '')
    search_query = request.GET.get('query', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    page = request.GET.get('page', 1)

    # Filter tournaments based on query parameters
    tournaments = Tournament.objects.all()

    if search_query:
        tournaments = tournaments.filter(name__icontains=search_query)

    if selected_state:
        tournaments = tournaments.filter(state=selected_state)

    if start_date:
        tournaments = tournaments.filter(start_date__gte=start_date)

    if end_date:
        tournaments = tournaments.filter(end_date__lte=end_date)

    # Paginate the tournaments
    paginator = Paginator(tournaments, 10)  # Show 10 tournaments per page
    paginated_tournaments = paginator.get_page(page)

    # Define the available states
    state_options = [
        {'key': 'created', 'title': 'Upcoming'},
        {'key': 'inprogress', 'title': 'In Progress'},
        {'key': 'completed', 'title': 'Completed'},
    ]

    # Pass data to the template
    context = {
        'tournaments': paginated_tournaments,
        'states': state_options,
        'selected_state': selected_state,
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
        'total_pages': paginator.num_pages,
        'current_page': paginated_tournaments.number,
    }

    return render(request, 'portal/tournament/my_tournaments.html', context)
