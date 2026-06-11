from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from core.user.models import User
from core.mail.models import Invite
from core.ratelimit import rate_limit

@login_required
def friend_search(request):
    # Pending invites the user can act on — bundled count covers both
    # match and friend invites so the badge reflects all action items
    # without needing a per-type breakdown on this page.
    pending_invites_count = Invite.objects.filter(
        player=request.user,
        state='sent',
        type__in=('match', 'friend'),
    ).count()

    # Outgoing friend requests the user has sent — surfaced separately so
    # they know they're waiting on the other side.
    outgoing_friend_requests = Invite.objects.filter(
        sender=request.user, type='friend', state='sent',
    ).select_related('player').order_by('-invited_date')

    context = {
        'user_friend_code': request.user.friend_code,
        'friends': request.user.friends.all().order_by('username'),
        'pending_invites_count': pending_invites_count,
        'outgoing_friend_requests': outgoing_friend_requests,
    }

    if request.method == 'POST':
        if 'friend_code' in request.POST:  # Search functionality
            friend_code = request.POST.get('friend_code')
            if friend_code:
                found_user = User.find_by_friend_code(friend_code)
                if found_user:
                    context['found_user'] = found_user
                    context['is_friend'] = request.user.is_friend(found_user)
                else:
                    messages.error(request, 'No user found with that friend code.')

    return render(request, 'portal/user/friend_search.html', context)

@login_required(login_url='/auth/login/')
# Friend requests notify the target — cap per user (plan §7.5 item 3).
@rate_limit("friend-request", 30, 3600, per="user")
def add_friend_action(request, user_id):
    """Send a *friend request* — bilateral friendship only happens after the
    target user accepts. Replaces the old "click Add → instantly friends"
    flow which trusted strangers (issues-part-2 §1)."""
    if request.method != 'POST':
        return redirect('core-portal:friend_search')

    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('core-portal:friend_search')

    if target == request.user:
        messages.error(request, "You can't add yourself.")
        return redirect('core-portal:friend_search')

    if request.user.is_friend(target):
        messages.info(request, f"You're already friends with {target.username}.")
        return redirect('core-portal:friend_search')

    # If a pending invite already exists in either direction, don't spam.
    existing = Invite.objects.filter(
        type='friend', state='sent',
    ).filter(
        models.Q(sender=request.user, player=target)
        | models.Q(sender=target, player=request.user)
    ).first()
    if existing:
        if existing.sender == request.user:
            messages.info(request, f'You already sent a friend request to {target.username}.')
        else:
            messages.info(
                request,
                f'{target.username} already sent you a request — '
                f'accept it from your invites list.',
            )
        return redirect('core-portal:friend_search')

    Invite.objects.create_invite(
        obj_id=None,
        sender=request.user,
        player=target,
        invite_type='friend',
        invited_date=timezone.now(),
    )
    messages.success(
        request,
        f'Friend request sent to {target.username}. They have to accept '
        f'before you become friends.',
    )
    return redirect('core-portal:friend_search')

@login_required
def remove_friend_action(request, friend_id):
    if request.method == 'POST':
        friend = get_object_or_404(User, id=friend_id)
        request.user.friends.remove(friend)
        messages.success(request, f'Removed {friend.name} from your friends list.')
    return redirect('core-portal:friend_search')

