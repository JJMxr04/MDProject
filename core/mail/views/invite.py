# views.py
import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_GET, require_POST

from core.mail.forms import InviteForm
from core.mail.models import Emails, Invite, Notification, PendingInvite
from core.mail.models.invites import InviteExpired
from core.mail.serializers.notification import NotificationSerializer
from core.ratelimit import rate_limit
from core.user.models import User


@login_required(login_url='/auth/login/')
@rate_limit("create-invite", 30, 3600, per="user")
def create_invite(request):
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            # Only the player-to-player types are creatable here. Tournament
            # invites are admin-issued (tournament admin view) — a client-
            # supplied type='tournament' with an arbitrary obj_id would blow
            # up in the manager's Tournament lookup.
            if cleaned.get('type') not in ('match', 'friend'):
                return redirect('core-portal:portal-public-match-list')
            # Route through the manager so the matching Emails.send_*
            # call fires. The ModelForm path (form.save() + invite.save())
            # bypasses InviteManager.create_invite() and the email never
            # goes out — same trap that hit the waitlist signup form.
            # ``accepted`` is never client-settable — a pre-accepted invite
            # row is a mass-assignment hole. create_invite is the single
            # creatability choke-point: a match invite that can't be built
            # right now is rejected here so the sender sees why instead of
            # stranding the recipient with an un-acceptable invite.
            from django.contrib import messages

            from core.game.models.game import (
                FixtureUnavailable,
                GoldenGameUnavailable,
            )
            try:
                Invite.objects.create_invite(
                    obj_id=None,
                    player=cleaned.get('player'),
                    invite_type=cleaned.get('type'),
                    sender=request.user,
                    accepted=False,
                    invited_date=timezone.now(),
                )
            except (FixtureUnavailable, GoldenGameUnavailable) as exc:
                messages.error(request, str(exc))
                return redirect('core-portal:portal-public-match-list')
            return redirect('core-portal:invite-success')
    else:
        form = InviteForm()

    return redirect('core-portal:portal-public-match-list')


@require_POST
@login_required(login_url='/auth/login/')
def accept_invite(request, invite_id):
    """Invite action endpoint: accept / reject (decline) by the recipient,
    cancel (withdraw) by the sender."""
    from core.game.models.game import FixtureUnavailable, GoldenGameUnavailable
    from core.match.duels import DuelError
    from core.tournament.models.tournament import TournamentJoinUnavailable

    try:
        invite = Invite.objects.get(id=invite_id)
        data = json.loads(request.body)
        action = data.get('action')

        # Per-action authorization: the recipient accepts/declines, the
        # sender cancels — nobody else touches the row.
        actor = invite.player if action in ('accept', 'reject') else invite.sender
        if request.user != actor:
            return JsonResponse({'error': 'You are not authorized to perform this action.'}, status=403)

        if action == 'accept':
            try:
                Invite.objects.accept_invite(invite)
            except (GoldenGameUnavailable, FixtureUnavailable,
                    TournamentJoinUnavailable, InviteExpired, DuelError) as exc:
                # Domain failure (catalog can't seed / window not viable /
                # tournament can't take the player / invite expired).
                # Surface the message verbatim so the portal toast is
                # meaningful. Except for expiry, the atomic rollback
                # restored the invite to its sent state.
                return JsonResponse({'error': str(exc)}, status=400)
            return JsonResponse({'success': 'Invite accepted.'})
        elif action == 'reject':
            Invite.objects.decline_invite(invite)
            return JsonResponse({'success': 'Invite declined.'})
        elif action == 'cancel':
            Invite.objects.cancel_invite(invite)
            return JsonResponse({'success': 'Invite canceled.'})
        else:
            return JsonResponse({'error': 'Invalid action.'}, status=400)
    except Invite.DoesNotExist:
        return JsonResponse({'error': 'Invite not found.'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data.'}, status=400)
    except Exception:
        return JsonResponse({'error': 'An unexpected error occurred.'}, status=400)


@require_POST
@login_required(login_url='/auth/login/')
# Shares the create-invite budget — email invites are still invites:
# throttle through the existing budget.
@rate_limit("create-invite", 30, 3600, per="user")
def invite_by_email(request):
    """Invite someone who may not have an account yet.

    POST JSON: {"email": ..., "invite_type": "friend"|"match",
    "format": "BLITZ"|...}. If the email already belongs to a user, this
    routes to a normal friend/match invite instead — one entry point, the
    server picks the right mechanism.
    """
    from core.match import formats

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid request data.'}, status=400)

    email = (data.get('email') or '').strip().lower()
    invite_type = data.get('invite_type') or 'friend'
    if '@' not in email or len(email) > 254:
        return JsonResponse({'error': 'Enter a valid email address.'}, status=400)
    if invite_type not in ('friend', 'match'):
        return JsonResponse({'error': 'Invalid invite type.'}, status=400)
    payload = {}
    if invite_type == 'match':
        payload['format'] = formats.normalize_format(data.get('format'))

    if email == request.user.email.lower():
        return JsonResponse({'error': "That's your own email address."}, status=400)

    existing_user = User.objects.filter(email__iexact=email).first()
    if existing_user is not None:
        if invite_type == 'friend' and request.user.is_friend(existing_user):
            return JsonResponse({'error': "You're already friends with them."}, status=400)
        pending = Invite.objects.filter(
            sender=request.user, player=existing_user,
            type=invite_type, state='sent',
        ).first()
        if pending is None:
            # create_invite is the single creatability choke-point — a match
            # invite that can't be built right now is rejected here rather
            # than emailing an un-acceptable challenge.
            from core.game.models.game import (
                FixtureUnavailable,
                GoldenGameUnavailable,
            )
            try:
                Invite.objects.create_invite(
                    obj_id=None,
                    player=existing_user,
                    invite_type=invite_type,
                    sender=request.user,
                    payload=payload,
                )
            except (FixtureUnavailable, GoldenGameUnavailable) as exc:
                return JsonResponse({'error': str(exc)}, status=400)
        return JsonResponse({
            'success': 'They already have an account — a regular invite was sent.',
            'existing_user': True,
        })

    pending, created = PendingInvite.objects.create_pending(
        inviter=request.user, email=email,
        invite_type=invite_type, payload=payload,
    )
    if created:
        signup_url = request.build_absolute_uri(
            reverse('core-auth:register') + f'?invite={pending.token}'
        )
        Emails.send_signup_invite(
            email, request.user.username, signup_url,
            format_label=formats.format_label(payload.get('format'))
            if invite_type == 'match' else None,
        )
        from core.metrics.models import track
        track(request.user, "invite_sent", invite_type=f"signup_{invite_type}",
              invite_id=str(pending.pk))
        return JsonResponse({'success': 'Invite email sent.'})
    return JsonResponse({
        'success': 'Already invited — their invite is still valid.',
    })


@login_required(login_url='/auth/login/')
def success_invite(request):
    return render(request, 'portal/notifications/invite/invite_success.html')


@login_required(login_url='/auth/login/')
def invite_list(request):
    user = request.user
    box = request.GET.get('box', 'received')
    if box not in ('received', 'sent'):
        box = 'received'
    search_query = request.GET.get('q', '').strip()

    incoming = (
        Invite.objects.filter(player=user)
        .select_related('sender')
        .order_by('-invited_date')
    )
    outgoing = (
        Invite.objects.filter(sender=user)
        .select_related('player')
        .order_by('-invited_date')
    )

    # Counts shown on the segments stay unfiltered by the search.
    received_count = incoming.count()
    sent_count = outgoing.count()

    if search_query:
        incoming = incoming.filter(sender__username__icontains=search_query)
        outgoing = outgoing.filter(player__username__icontains=search_query)

    content = {
        'invites': incoming,
        'outgoing_invites': outgoing,
        'box': box,
        'search_query': search_query,
        'received_count': received_count,
        'sent_count': sent_count,
    }

    return render(request, 'portal/notifications/invite/invite_list.html', content)
