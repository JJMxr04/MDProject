# views.py
from django.shortcuts import render, redirect
from core.mail.forms import InviteForm
from django.utils import timezone

from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from core.mail.models import Notification, Invite
from core.mail.serializers.notification import NotificationSerializer
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
import json


@login_required(login_url='/auth/login/')
def create_invite(request):
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            # Route through the manager so the matching Emails.send_*
            # call fires. The ModelForm path (form.save() + invite.save())
            # bypasses InviteManager.create_invite() and the email never
            # goes out — same trap that hit the waitlist signup form.
            Invite.objects.create_invite(
                obj_id=cleaned.get('obj_id'),
                player=cleaned.get('player'),
                invite_type=cleaned.get('type'),
                sender=request.user,
                accepted=cleaned.get('accepted', False),
                invited_date=timezone.now(),
            )
            return redirect('core-portal:invite-success')
    else:
        form = InviteForm()

    return redirect('core-portal:portal-public-match-list')


@require_POST
@login_required(login_url='/auth/login/')
def accept_invite(request, invite_id):
    from core.game.models.game import GoldenGameUnavailable

    try:
        invite = Invite.objects.get(id=invite_id)
        if request.user != invite.player:
            return JsonResponse({'error': 'You are not authorized to perform this action.'}, status=403)
        data = json.loads(request.body)
        if data.get('action') == 'accept':
            try:
                Invite.objects.accept_invite(invite)
            except GoldenGameUnavailable as exc:
                # Catalog can't seed a Golden Game right now. Atomic rollback
                # already restored the invite to its sent state — surface
                # the message verbatim so the portal toast is meaningful.
                return JsonResponse({'error': str(exc)}, status=400)
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
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=400)


@login_required(login_url='/auth/login/')
def success_invite(request):
    return render(request, 'portal/notifications/invite/invite_success.html')


@login_required(login_url='/auth/login/')
def invite_list(request):
    user = request.user
    invites = Invite.objects.filter(player=user).all()
    content = {
        'invites': invites
    }


    return render(request, 'portal/notifications/invite/invite_list.html', content)
