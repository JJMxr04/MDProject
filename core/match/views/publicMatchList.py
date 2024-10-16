from django.shortcuts import render
from django.core.paginator import Paginator
from core.match.models import Match  # Assuming you have a Match model
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404

from core.mail.forms import InviteForm, MatchInviteForm
from core.mail.models import Invite
from core.user.models import User


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
    form = MatchInviteForm()

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'total_pages': paginator.num_pages,
        'current_page': int(page),
        'form': form,
    }
    
    return render(request, 'portal/match/public_match_list.html', context)
@require_POST
@login_required(login_url='/auth/login/')
def create_public_match_view(request):
    print(request.POST)
    if request.method == 'POST':
        form = MatchInviteForm(request.POST)
        

        match_type = request.POST.get('type')  # Accessing cleaned data from form
        player = request.POST.get('player')  # Optional field, may be None
        owner = request.user

        if match_type == 'public':
            # Create a public match
            new_match = Match.objects.create(player_1=owner)
            return JsonResponse({'status': 'success', 'match_id': new_match.id})
        
        elif match_type == 'private':
            # Ensure the player is provided for private matches
            if not player:
                return JsonResponse({'status': 'error', 'message': 'Player is required for private matches'}, status=400)

            # Create the match
            player_2= User.objects.get(id=player)
            # Create the invite
            invite = Invite.objects.create(
                sender=owner,
                player=player_2,  # Add the invited player
                type='private'
            )

            return JsonResponse({'status': 'success', 'invite_id': invite.id})
        
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid match type'}, status=400)
    


@login_required(login_url='/auth/login/')
def public_match_detail_view(request, match_id):
    match = get_object_or_404(Match, id=match_id)


    context = {
        'match': match,


    }
    
    return render(request, 'portal/match/public_match_detail.html', context)

@require_POST
@login_required(login_url='/auth/login/')
def accept_public_match_view(request, match_id):
    print(1)
    data = json.loads(request.body)  # Decode and parse JSON body
    if data.get('action') == 'accept':  # Updated line
    # Create a new match
        print(2)
        try:
            print(3)
            user = request.user
            # Assuming you have a way to get Player objects from usernames
            print(4)
            match = Match.objects.get(id=match_id)
            print(5)
            a_match = Match.objects.accept_match(match,user)
            print(6)
            # Redirect or return a response after creation
            print(7)



            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    else:
        return JsonResponse({'status': 'error', 'message': 'Not the correct action'}, status=400)
    
