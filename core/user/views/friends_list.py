from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.user.models import User

@login_required
def friend_search(request):
    context = {
        'user_friend_code': request.user.friend_code,
        'friends': request.user.friends.all()  # Add this line to get all friends
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
def add_friend_action(request, user_id):
    if request.method == 'POST':
        friend = User.objects.get(id=user_id)
        request.user.add_friend(friend)
        friend.add_friend(request.user)
        messages.success(request, f'You are now friends with {friend.name}!')
    return redirect('core-portal:friend_search')

@login_required
def remove_friend_action(request, friend_id):
    if request.method == 'POST':
        friend = get_object_or_404(User, id=friend_id)
        request.user.friends.remove(friend)
        messages.success(request, f'Removed {friend.name} from your friends list.')
    return redirect('core-portal:friend_search')

