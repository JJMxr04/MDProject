from django.shortcuts import render
from django.core.paginator import Paginator
from core.match.models import Match  # Assuming you have a Match model
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST


@login_required(login_url='/auth/login/')
def public_match_list_view(request):
    search_query = request.GET.get('search', '')
    page = request.GET.get('page', 1)

    # Filter the matches based on search query, state, and date range
    matches = Match.objects.filter(match_state='created')

    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)
    
    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'total_pages': paginator.num_pages,
        'current_page': int(page)
    }
    
    return render(request, 'portal/match/public_match_list.html', context)


@require_POST
@login_required(login_url='/auth/login/')
def create_public_match_view(request):


    
    # Create a new match
    try:
        owner = request.user
        
        # Assuming you have a way to get Player objects from usernames


        new_match = Match.objects.create(player_1=player_1)
        new_match.save()

        # Redirect or return a response after creation




        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
