# views.py
from django.shortcuts import render, redirect
from core.mail.forms import InviteForm
from django.utils import timezone

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from core.mail.models import Notification
from core.mail.serializers.notification import NotificationSerializer
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse


@login_required(login_url='/auth/login/')
def create_invite(request):
    print(request.body)
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            invite = form.save(commit=False)
            invite.sender = request.user  # Automatically set the sender to the current user
            invite.invited_date = timezone.now()  # Set the invited date to now
            invite.save()
            return redirect('core-portal:invite_success')  # Redirect to a success page or wherever you want
    else:
        form = InviteForm()

    return redirect('core-portal:portal-public-match-list')


@require_POST
@login_required(login_url='/auth/login/')
def accept_invite(request, invite_id):
    try:
        invite = Invite.objects.get(id=invite_id)

        # Check if the user is the invited player
        if request.user != invite.player:
            return JsonResponse({'error': 'You are not authorized to perform this action.'}, status=403)

        # Parse the request body
        data = json.loads(request.body)

        # Handle actions
        if data.get('action') == 'accept':
            Invite.objects.accept_invite(invite)
            return JsonResponse({'success': 'Invite accepted.'})
        elif data.get('action') == 'reject':
            Invite.objects.delete_invite(invite)
            return JsonResponse({'success': 'Invite rejected.'})
        else:
            return JsonResponse({'error': 'Invalid action.'}, status=400)

    except Invite.DoesNotExist:
        return JsonResponse({'error': 'Invite not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data.'}, status=400)
    except Exception:
        # Return a 400 error for any other unexpected error
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=400)


@login_required(login_url='/auth/login/')
def success_invite(request):
    return render('portl/notifications/invite/invite_success.html')
