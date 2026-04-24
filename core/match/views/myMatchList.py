from django.shortcuts import render
from django.core.paginator import Paginator
from core.match.models import Match  # Assuming you have a Match model
from django.db.models import Q

def my_match_list_view(request):
    search_query = request.GET.get('search', '')
    state = request.GET.get('state', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    page = request.GET.get('page', 1)

    # Filter the matches based on search query, state, and date range


    matches = Match.objects.filter(Q(player_1=request.user) | Q(player_2=request.user))


    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)
    
    if state:
        matches = matches.filter(match_state=state)

    if start_date:
        matches = matches.filter(start_date__gte=start_date)

    if end_date:
        matches = matches.filter(end_date__lte=end_date)

    matches = matches.order_by('-start_date')

    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)

    # Annotate each match on the page with the opponent from the viewer's POV.
    user = request.user
    for match in matches_page.object_list:
        match.opponent = match.player_2 if match.player_1_id == user.id else match.player_1

    quick_filters = [
        {"label": "All",         "value": "",          "is_active": state == ""},
        {"label": "Pending",     "value": "created",   "is_active": state == "created"},
        {"label": "In Progress", "value": "accepted",  "is_active": state == "accepted"},
        {"label": "Completed",   "value": "completed", "is_active": state == "completed"},
    ]

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'state': state,
        'start_date': start_date,
        'end_date': end_date,
        'quick_filters': quick_filters,
        'total_pages': paginator.num_pages,
        'current_page': int(page)
    }
    
    return render(request, 'portal/match/my_match_list.html', context)
