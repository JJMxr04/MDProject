from django.shortcuts import render
from django.core.paginator import Paginator
from core.match.models import Match  # Assuming you have a Match model

def my_match_list_view(request):
    search_query = request.GET.get('search', '')
    state = request.GET.get('state', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    page = request.GET.get('page', 1)

    # Filter the matches based on search query, state, and date range
    matches = Match.objects.all()

    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)
    
    if state:
        matches = matches.filter(state=state)
    
    if start_date:
        matches = matches.filter(start_date__gte=start_date)
    
    if end_date:
        matches = matches.filter(end_date__lte=end_date)
    
    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'state': state,
        'start_date': start_date,
        'end_date': end_date,
        'total_pages': paginator.num_pages,
        'current_page': int(page)
    }
    
    return render(request, 'portal/match/my_match_list.html', context)
