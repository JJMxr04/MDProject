from django.shortcuts import render
from django.core.paginator import Paginator
from core.match.models import Match  # Assuming you have a Match model
from django.contrib.auth.decorators import login_required
import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import get_object_or_404

from core.mail.forms import InviteForm, MatchInviteForm
from core.mail.models import Invite
from core.ratelimit import rate_limit
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
        .select_related("player_1", "player_2")
        .order_by('-start_date')
    )

    if search_query:
        matches = matches.filter(player_1__username__icontains=search_query) | \
                  matches.filter(player_2__username__icontains=search_query)

    # Paginate the matches
    paginator = Paginator(matches, 10)  # Show 10 matches per page
    matches_page = paginator.get_page(page)

    # Creator flair (phase 8): level + current-season division, one query each.
    from core.ranking.standings import divisions_for, levels_for
    creator_ids = [m.player_1_id for m in matches_page.object_list]
    levels = levels_for(creator_ids)
    divisions = divisions_for(creator_ids)
    for match in matches_page.object_list:
        match.creator_level = levels.get(match.player_1_id)
        match.creator_division = divisions.get(match.player_1_id)

    form = MatchInviteForm()

    # Friends list is needed so the Create-match modal can offer "challenge
    # a specific friend" without making the user navigate to /friends first.
    friends = list(request.user.friends.all().order_by('username'))

    from core.match import formats
    match_formats = [
        {'key': key, 'label': cfg['label'], 'days': cfg['days'],
         'games': cfg['games_per_player']}
        for key, cfg in formats.MATCH_FORMATS.items()
    ]

    context = {
        'matches': matches_page,
        'search_query': search_query,
        'total_pages': paginator.num_pages,
        'current_page': int(page),
        'form': form,
        'friends': friends,
        'match_formats': match_formats,
        'default_format': formats.DEFAULT_FORMAT,
    }

    return render(request, 'portal/match/public_match_list.html', context)
@require_POST
@login_required(login_url='/auth/login/')
# Each private create fires an invite email — cap the blast radius per user
# (plan §7.5 item 3). Runs after login_required so it keys on the user.
@rate_limit("create-match", 30, 3600, per="user")
def create_public_match_view(request):
    from core.game.models import Game
    from core.game.models.game import FixtureUnavailable, GoldenGameUnavailable
    from core.match import formats

    if request.method == 'POST':
        form = MatchInviteForm(request.POST)


        match_type = request.POST.get('type')  # Accessing cleaned data from form
        player = request.POST.get('player')  # Optional field, may be None
        # Format preset (D-5 #4): fixed here, displayed on the invite,
        # accept = consent. Unknown values normalize to the default.
        match_format = formats.normalize_format(request.POST.get('format'))
        owner = request.user

        if match_type == 'public':
            # Create a public match via the manager — it gates on fixture
            # availability + the events catalog (no events with markets →
            # no match) and stamps start/end dates from the format window.
            try:
                new_match = Match.objects.create_match(owner, match_format=match_format)
            except (GoldenGameUnavailable, FixtureUnavailable) as exc:
                return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
            return JsonResponse({'status': 'success', 'match_id': new_match.id})

        elif match_type == 'private':
            # Ensure the player is provided for private matches
            if not player:
                return JsonResponse({'status': 'error', 'message': 'Player is required for private matches'}, status=400)

            # The id comes straight from the client form — validate it like
            # the friend-request flow does (friends_list.add_friend_action)
            # instead of 500ing on a forged/stale uuid. A malformed uuid
            # raises ValidationError from the UUIDField lookup.
            from django.core.exceptions import ValidationError
            try:
                player_2 = User.objects.get(id=player)
            except (User.DoesNotExist, ValidationError, ValueError):
                return JsonResponse({'status': 'error', 'message': 'Player not found.'}, status=404)

            if player_2 == owner:
                return JsonResponse({'status': 'error', 'message': 'You cannot challenge yourself.'}, status=400)

            # One pending *match* challenge per pair — a resend just re-points
            # the user at the invite that's already waiting. Duels are
            # independent (they're per event+market, and many can be pending),
            # so a waiting duel must not be mistaken for a pending match.
            # ``has_key`` (not ``payload__duel=True``): regular match invites
            # have no ``duel`` key, and excluding on a value lookup would drop
            # them too via JSON NULL semantics.
            existing = Invite.objects.filter(
                sender=owner, player=player_2, type='match', state='sent',
            ).exclude(payload__has_key='duel').first()
            if existing:
                return JsonResponse({'status': 'success', 'invite_id': existing.id})

            # Fixture-availability check at creation (D-5 #2) — a Blitz
            # invite into an empty midweek window is rejected here with a
            # useful message instead of failing at accept time.
            try:
                Game.objects.assert_window_viable(match_format=match_format)
            except FixtureUnavailable as exc:
                return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

            # Create the invite — the format rides on the payload and the
            # accept path threads it into create_match (Phase 5 §2).
            invite = Invite.objects.create_invite(
                obj_id=None,
                sender=owner,
                player=player_2,  # Add the invited player
                invite_type='match',
                payload={'format': match_format},
            )

            return JsonResponse({'status': 'success', 'invite_id': invite.id})

        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid match type'}, status=400)


@require_GET
@login_required(login_url='/auth/login/')
def match_availability_view(request):
    """Pre-submit availability check for the create-match UI (D-5 #2):
    "N games available in this window" before the user commits."""
    from core.game.models import Game
    from core.game.models.game import FixtureUnavailable
    from core.match import formats
    from django.utils import timezone

    match_format = formats.normalize_format(request.GET.get('format'))
    needed = formats.min_distinct_events(match_format)
    try:
        available = Game.objects.count_available_events(
            window_end=timezone.now() + formats.format_window(match_format),
        )
    except FixtureUnavailable as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=503)
    return JsonResponse({
        'status': 'success',
        'format': match_format,
        'available': available,
        'needed': needed,
        'viable': available >= needed,
    })
    


@login_required(login_url='/auth/login/')
def public_match_detail_view(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related("player_1", "player_2"), id=match_id
    )

    # If the viewer is already in the match, the actual pick UI lives on
    # /portal/match/<id>/ (my_match_detail). We expose a link to it here
    # instead of duplicating the 1000+ line pick modal.
    is_player_in_match = (
        request.user.is_authenticated
        and (request.user == match.player_1 or request.user == match.player_2)
    )

    # Access control (findings.md S-4b): this is the *public join* page. A
    # match is only viewable here if it's still open to join (state='created')
    # OR the viewer is one of its players. Otherwise a logged-in user could
    # read any match by id (opponent, result, picks) -> IDOR. 404 (not 403)
    # so we don't leak that the match exists.
    if match.match_state != 'created' and not is_player_in_match:
        from django.http import Http404
        raise Http404("No Match matches the given query.")

    from core.ranking.standings import divisions_for, levels_for
    ids = [match.player_1_id, match.player_2_id]
    levels = levels_for(ids)
    divisions = divisions_for(ids)

    context = {
        'match': match,
        'is_player_in_match': is_player_in_match,
        'player_1_level': levels.get(match.player_1_id),
        'player_2_level': levels.get(match.player_2_id),
        'player_1_division': divisions.get(match.player_1_id),
        'player_2_division': divisions.get(match.player_2_id),
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
    
