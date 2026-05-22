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

    # Don't show the user's own open public matches in the "join one" list
    # — they can't accept their own. Same goes for matches they've already
    # accepted (those move out of state='created' anyway).
    matches = (
        Match.objects.filter(match_state='created')
        .exclude(player_1=request.user)
        .order_by('-start_date')
    )

    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)

    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)
    form = MatchInviteForm()

    # Friends list is needed so the Create-match modal can offer "challenge
    # a specific friend" without making the user navigate to /friends first.
    friends = list(request.user.friends.all().order_by('username'))

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'total_pages': paginator.num_pages,
        'current_page': int(page),
        'form': form,
        'friends': friends,
    }

    return render(request, 'portal/match/public_match_list.html', context)
@require_POST
@login_required(login_url='/auth/login/')
def create_public_match_view(request):
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
            invite = Invite.objects.create_invite(
                obj_id=None,
                sender=owner,
                player=player_2,  # Add the invited player
                invite_type='match'
            )

            return JsonResponse({'status': 'success', 'invite_id': invite.id})
        
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid match type'}, status=400)
    


@login_required(login_url='/auth/login/')
def public_match_detail_view(request, match_id):
    match = get_object_or_404(Match, id=match_id)

    # If the viewer is already in the match, the actual pick UI lives on
    # /portal/match/<id>/ (my_match_detail). We expose a link to it here
    # instead of duplicating the 1000+ line pick modal.
    is_player_in_match = (
        request.user.is_authenticated
        and (request.user == match.player_1 or request.user == match.player_2)
    )

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
    }

    return render(request, 'portal/match/public_match_detail.html', context)

@require_POST
@login_required(login_url='/auth/login/')
def accept_public_match_view(request, match_id):
    from core.game.models.game import GoldenGameUnavailable

    data = json.loads(request.body)
    if data.get('action') != 'accept':
        return JsonResponse({'status': 'error', 'message': 'Not the correct action'}, status=400)

    try:
        match = Match.objects.get(id=match_id)
    except Match.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Match not found.'}, status=404)

    try:
        Match.objects.accept_match(match, request.user)
    except GoldenGameUnavailable as exc:
        # Atomic rollback already happened in accept_match — pass the user-
        # facing message straight through to the portal toast.
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'success'})
    
